import { planJob } from './automation/planner.js';
import {parse} from '@tracespace/parser'
import {fromTriangles, applyToPoint} from 'transformation-matrix';

const MATCH_TOLERANCE_MM = 0.001;

function validateTriangle(points, label) {
    if (!Array.isArray(points) || points.length !== 3 || points.some(p =>
        !Array.isArray(p) || p.length !== 2 || !p.every(Number.isFinite))) {
        throw new Error(`${label} requires three finite XY fiducials`);
    }
    const [a, b, c] = points;
    const cross = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]);
    const scale = Math.max(...points.flatMap(p => points.map(q => Math.hypot(p[0] - q[0], p[1] - q[1]))));
    if (!Number.isFinite(cross) || Math.abs(cross) <= Math.max(1e-9, scale * scale * 1e-9)) {
        throw new Error(`${label} requires distinct, noncollinear fiducials`);
    }
}

class Point {
    constructor(x, y, z) {

        //these are the raw positions from the gerber import
        this.x = x;
        this.y = y;
        this.z = z;

        // these are any calibrated positions as a result from fid cal
        this.calX = null;
        this.calY = null;

        // this is where on the canvas the dot was drawn for this point
        this.canvasX = null;
        this.canvasY = null;

        // this is the dom object for the little card in the point list
        this.docElement = null;
    }

    toArray() {
        return [this.x, this.y, this.z];
    }

    static fromArray(arr) {
        return new Point(arr[0], arr[1], arr[2]);
    }

}

class Fiducial extends Point {
    constructor(x, y, z, searchX, searchY) {
        super(x, y, z)
        this.searchX = searchX;
        this.searchY = searchY;
    }

}

export class Job {
    constructor(lumen, toast) {

        this.coordinateFrame = null;
        this.placements = [];
        this.fiducials = [];

        this.dispenseDegrees = 30;
        this.retractionDegrees = 1;
        this.dwellMilliseconds = 100;
        this.preGcode = "";
        this.postGcode = "";
        this.invertDispense = false;
        this.lumen = lumen;
        this.toast = toast;

        this.jobCanvas = document.getElementById('pointViz');

        this.clickedFidBuffer = [];
    }

    // this does a few things
    // it takes all the points and fids in a job, and draws them on the canvas
    // it also saves all the drawn positions to the point and fid objects for easier click detection
    //
    drawJobToCanvas(){


        // const rect = this.jobCanvas.getBoundingClientRect();
        // this.jobCanvas.width = rect.width;
        // this.jobCanvas.height = rect.height;
        // this.jobCanvas.style.width = `${rect.width}px`;
        // this.jobCanvas.style.height = `${rect.height}px`;

        const ctx = this.jobCanvas.getContext("2d");

        // Find bounds of all points
        let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
        for (const point of this.placements) {

            minX = Math.min(minX, point.x);
            minY = Math.min(minY, point.y);
            maxX = Math.max(maxX, point.x);
            maxY = Math.max(maxY, point.y);
        }

        for (const point of this.fiducials) {
            minX = Math.min(minX, point.x);
            minY = Math.min(minY, point.y);
            maxX = Math.max(maxX, point.x);
            maxY = Math.max(maxY, point.y);
        }

        if (!Number.isFinite(minX)) {
            ctx.clearRect(0, 0, this.jobCanvas.width, this.jobCanvas.height);
            return;
        }
        // Add a small margin to the bounds
        const margin = Math.max(maxX - minX, maxY - minY, 1) * 0.1; // 10% margin
        minX -= margin;
        minY -= margin;
        maxX += margin;
        maxY += margin;

        const width = maxX - minX;
        const height = maxY - minY;

        // Calculate scale to fit the canvas while maintaining aspect ratio
        const scaleX = this.jobCanvas.width / width;
        const scaleY = this.jobCanvas.height / height;
        const vizScale = Math.min(scaleX, scaleY);

        // Calculate shifts to center the points
        const xShift = -minX;
        const yShift = -minY;

        // Clear canvas
        ctx.clearRect(0, 0, this.jobCanvas.width, this.jobCanvas.height);

        // Draw fid points in blue
        ctx.fillStyle = "blue";
        for (let point of this.fiducials) {

            const newX = (point.x + xShift) * vizScale;
            const newY = (point.y + yShift) * vizScale;

            point.canvasX = newX;
            point.canvasY = newY;

            ctx.beginPath();
            ctx.arc(newX, this.jobCanvas.height - newY, 2, 0, Math.PI * 2);
            ctx.fill();

        }

        // Draw paste points in red
        ctx.fillStyle = "red";
        for (let point of this.placements) {
            const newX = (point.x + xShift) * vizScale;
            const newY = (point.y + yShift) * vizScale;

            point.canvasX = newX;
            point.canvasY = newY;

            ctx.beginPath();
            ctx.arc(newX, this.jobCanvas.height - newY, 2, 0, Math.PI * 2);
            ctx.fill();
        }

    }

    // returns the closest point object to a click coordinate on the canvas
    returnClosestFidFromClickCoordinates(clickX, clickY){
        // Find the closest point within a larger threshold
        const threshold = 10.0; // 2mm threshold for easier clicking
        let closestPoint = null;
        let minDistance = Infinity;

        // Only check fid points
        for (const point of this.fiducials) {
            // console.log("checking against: ", point.canvasX, point.canvasY)
            const distance = Math.sqrt(
                Math.pow(point.canvasX - clickX, 2) +
                Math.pow(point.canvasY - clickY, 2)
            );
            if (distance < threshold && distance < minDistance) {
                minDistance = distance;
                closestPoint = point;
            }
        }

        return closestPoint;

    }

    async parseGerber(fileInputId) {
        const file = document.getElementById(fileInputId)?.files?.[0];
        if (!file) throw new Error(`Select a Gerber file for ${fileInputId}`);
        const tree = parse(await file.text());
        if (tree.filetype !== 'gerber') throw new Error('Expected a Gerber file');
        let format, units, suppression;
        let x, y;
        const positions = [];
        const coordinate = raw => {
            if (!format || !units) throw new Error('Gerber must declare absolute coordinate format and units');
            const text = String(raw);
            if (!/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$/.test(text)) throw new Error('Invalid Gerber coordinate');
            const sign = text.startsWith('-') ? -1 : 1;
            let digits = text.replace(/^[+-]/, '');
            let value;
            if (digits.includes('.')) value = Number(text);
            else {
                if (suppression === 'trailing') digits = digits.padEnd(format[0] + format[1], '0');
                value = sign * Number(digits) / 10 ** format[1];
            }
            value *= units;
            if (!Number.isFinite(value)) throw new Error('Nonfinite Gerber coordinate');
            return value;
        };
        for (const child of tree.children) {
            if (child.type === 'units') {
                if (!['mm', 'in'].includes(child.units)) throw new Error('Unsupported Gerber units');
                units = child.units === 'in' ? 25.4 : 1;
            } else if (child.type === 'coordinateFormat') {
                if (child.mode !== 'absolute' || !Array.isArray(child.format) ||
                    child.format.length !== 2 || !child.format.every(n => Number.isInteger(n) && n >= 0)) {
                    throw new Error('Gerber requires an explicit absolute coordinate format');
                }
                format = child.format;
                suppression = child.zeroSuppression;
            } else if (child.type === 'graphic') {
                // D02 moves (and mask outlines) also establish modal X/Y references.
                if (child.coordinates.x !== undefined) x = coordinate(child.coordinates.x);
                if (child.coordinates.y !== undefined) y = coordinate(child.coordinates.y);
                if (child.graphic === 'shape') {
                    if (![x, y].every(Number.isFinite)) throw new Error('Gerber flash lacks a reference X or Y');
                    positions.push({ x, y });
                } else if (child.graphic !== 'move' && fileInputId === 'pasteGerberFile') {
                    throw new Error('Paste Gerber paths/regions are unsupported; export flashed pad apertures');
                }
            }
        }
        if (!positions.length) throw new Error('Gerber contains no flashed pads');
        return positions;
    }

    async loadJobFromGerbers() {
        if (this.loadingGerbers) throw new Error('Gerber import is already in progress');
        this.loadingGerbers = true;
        let clickHandler;
        try {
            const pastePoints = await this.parseGerber('pasteGerberFile');
            const maskPoints = await this.parseGerber('maskGerberFile');
            const onlyInMask = maskPoints.filter(mask => !pastePoints.some(paste =>
                Math.hypot(mask.x - paste.x, mask.y - paste.y) <= MATCH_TOLERANCE_MM));
            this.coordinateFrame = null;
            this.clickedFidBuffer = [];
            this.placements = pastePoints.map(p => new Point(p.x, p.y, 31.5));
            this.fiducials = onlyInMask.map(p => new Point(p.x, p.y, 31.5));
            this.loadJobIntoPositionList();
            if (this.fiducials.length < 3) throw new Error('Need at least three mask-only fiducials');
            this.drawJobToCanvas();
            clickHandler = event => {
                const rect = this.jobCanvas.getBoundingClientRect();
                const x = (event.clientX - rect.left) * this.jobCanvas.width / rect.width;
                const y = this.jobCanvas.height - (event.clientY - rect.top) * this.jobCanvas.height / rect.height;
                const closest = this.returnClosestFidFromClickCoordinates(x, y);
                if (closest) this.toast.receivedInput = closest;
            };
            this.jobCanvas.addEventListener('click', clickHandler);
            const selected = [];
            for (let i = 0; i < 3; i++) {
                this.toast.receivedInput = undefined;
                const fid = await this.toast.show(`Please click on FID${i + 1} in the display.`);
                if (!fid) throw new Error('Fiducial selection cancelled');
                if (!this.fiducials.includes(fid) || selected.includes(fid)) {
                    throw new Error('Select three distinct fiducials');
                }
                selected.push(fid);
            }
            validateTriangle(selected.map(f => [f.x, f.y]), 'Board registration');
            this.fiducials = selected;
            this.loadJobIntoPositionList();
            this.drawJobToCanvas();
        } finally {
            if (clickHandler) this.jobCanvas.removeEventListener('click', clickHandler);
            this.toast.receivedInput = undefined;
            this.loadingGerbers = false;
        }
    }

    async findBoardRoughPosition(){
        // request in toast to jog to fid1
        await this.toast.show("Please jog the camera to be centered on FID1.");

        // upon hitting continue, grab current position, save to fid1 searchXY
        const fid1Rough = await this.lumen.grabBoardPosition();

        console.log("fid1Rough: ", fid1Rough)

        this.fiducials[0].searchX = parseFloat(fid1Rough[0]);
        this.fiducials[0].searchY = parseFloat(fid1Rough[1]);

        // repeat for fid2 and fid3
        await this.toast.show("Please jog the camera to be centered on FID2.");
        const fid2Rough = await this.lumen.grabBoardPosition();
        this.fiducials[1].searchX = parseFloat(fid2Rough[0]);
        this.fiducials[1].searchY = parseFloat(fid2Rough[1]);

        await this.toast.show("Please jog the camera to be centered on FID3.");
        const fid3Rough = await this.lumen.grabBoardPosition();
        this.fiducials[2].searchX = parseFloat(fid3Rough[0]);
        this.fiducials[2].searchY = parseFloat(fid3Rough[1]);

        // ask to jog tip directly touching top surface
        await this.toast.show("Please jog the paste extruder tip to just barely touch the board.");

        // grab z pos and add .2 mm or something
        let zPos = await this.lumen.grabBoardPosition();

        await this.lumen.serial.send(["G0 Z31.5"]);

        zPos = parseFloat(zPos[2]) - 0.2;

        // save that position to every placement
        for(const placement of this.placements){
            placement.z = zPos
        }

        console.log(`this.fiducials: `, this.fiducials)

        this.transformPlacements([
            [this.fiducials[0].searchX, this.fiducials[0].searchY],
            [this.fiducials[1].searchX, this.fiducials[1].searchY],
            [this.fiducials[2].searchX, this.fiducials[2].searchY]
        ]);

        console.log(this.placements);

        this.loadJobIntoPositionList()

    }

    async performTipCalibration(){
        await this.toast.show("Please jog the camera to be centered on any fiducial.");

        // upon hitting continue, grab current position, save to fid1 searchXY
        const camPos = await this.lumen.grabBoardPosition();

        await this.lumen.serial.send(["G0 Z31.5"]);

        await this.lumen.serial.goToRelative(-45,63);

        await this.lumen.serial.send(["G0 Z46.5"]);

        await this.toast.show("Please jog the nozzle tip to be perfectly centered on and touching the fiducial.");

        const nozPos = await this.lumen.grabBoardPosition();

        await this.lumen.serial.send(["G0 Z31.5"]);

        this.lumen.tipXoffset = nozPos[0] - camPos[0];
        this.lumen.tipYoffset = nozPos[1] - camPos[1];

    }

    async performFiducialCalibration(){
        // lots of checks first
        if(this.fiducials.length !== 3){
            console.error("No fids in this job, cannot perform fiducial calibration.");
            return;
        }

        let fidActual = [];
        // go through and capture the actual positions of the fids
        // then we can perform the transformation

        for(let i = 0; i < this.fiducials.length; i++){
            const fid = this.fiducials[i];
            console.log(`Processing fiducial ${i + 1}:`, fid)
            console.log("jogging to fid: ", fid.searchX, fid.searchY)

            try {

                await this.lumen.serial.goTo(fid.searchX, fid.searchY);
                await new Promise(resolve => setTimeout(resolve, 1500));


                await this.lumen.jogToFiducial();
                await new Promise(resolve => setTimeout(resolve, 1500));

                await this.lumen.jogToFiducial();
                await new Promise(resolve => setTimeout(resolve, 1500));

                const fidReal = await this.lumen.grabBoardPosition();

                console.log(`Fiducial ${i + 1} final position:`, fidReal);
                fidActual.push([parseFloat(fidReal[0]), parseFloat(fidReal[1])])

                fid.calX = fidReal[0];
                fid.calY = fidReal[1];

            } catch (error) {
                console.error(`Error processing fiducial ${i + 1}:`, error);
                throw error;
            }
        }

        console.log("All fiducials processed, transforming placements...");
        this.transformPlacements(fidActual);

        console.log("fid cal complete: ", this.fiducials);

        this.loadJobIntoPositionList();


    }


    loadJobIntoPositionList(){
        // clear existing position elements
        const positionsList = document.querySelector('.positions-list');
        positionsList.innerHTML = '';

        // add new position elements
        for (let placement of this.placements) {
            this.createPositionElement(placement, false);
        }
        for (let fiducial of this.fiducials) {
            this.createPositionElement(fiducial, true);
        }
    }

    handleFiducialSelectionClick(event){
        const rect = this.jobCanvas.getBoundingClientRect();
        const clickX = (event.clientX - rect.left);
        const clickY = (event.clientY - rect.top);

        let closestPoint = this.returnClosestFidFromClickCoordinates(clickX, clickY);

        if (closestPoint) {
            ctx.beginPath();
            ctx.arc(closestPoint.canvasX, rect.height - closestPoint.canvasY, 6, 0, Math.PI * 2);
            ctx.fill();

            //store in buffer
            this.clickedFidBuffer.push(closestPoint);

            // Move to next fiducial or close modal
            currentFidIndex++;
            if (currentFidIndex < 3) {
                updateModalForFid();
            } else {
                // All fids captured, close modal
                modal.style.display = 'none';
                overlay.style.display = 'none';

                //moving clicked fids into this.fiducials
                this.fiducials = this.clickedFidBuffer;
                //wiping buffer
                this.clickedFidBuffer = [];

                console.log(this.fiducials);

                //removing event listener
                canvas.removeEventListener('click', this.handleFiducialSelectionClick)

            }
        }
    }

    async captureNewPosition() {
        console.log('Job capture method called');
        if (!this.lumen.serial) {
            console.error('Serial manager not set');
            return;
        }

        //TODO move almost all of this to lumen

        console.log('Serial manager is set, proceeding with capture');

        this.lumen.serial.clearInspectBuffer();
        console.log('Inspect buffer cleared');

        await this.lumen.serial.send(["G92"]);
        console.log('G92 command sent');

        const pattern = /X:(.*?) Y:(.*?) Z:(.*?) A:(.*?) B:(.*?) /;
        const re = new RegExp(pattern, 'i');

        console.log("Serial inspect buffer contents:", this.lumen.serial.inspectBuffer);

        for (var i = 0; i < this.lumen.serial.inspectBuffer.length; i++) {
            let currLine = this.lumen.serial.inspectBuffer[i];
            console.log('Checking line:', currLine);

            let result = re.test(currLine);
            console.log('Regex test result:', result);

            if(result) {
                const matches = re.exec(currLine);
                console.log('Position matches:', matches);
                this.addPoint(
                    parseFloat(matches[1]),
                    parseFloat(matches[2]),
                    parseFloat(matches[3])
                );
                console.log('Point added to job');

                this.loadJobIntoPositionList();
                return;
            }
        }
        console.log('No valid position found in inspect buffer');
    }

    addPoint(x, y, z) {
        let newPoint = new Point(x, y, z)
        this.placements.push(newPoint);
    }


    async importFromFile(file) {
        try {
            const jsonString = await new Promise((resolve, reject) => {
                const reader = new FileReader();
                reader.onload = (e) => resolve(e.target.result);
                reader.onerror = (error) => reject(error);
                reader.readAsText(file);
            });

            const data = JSON.parse(jsonString);

            if (!data || typeof data !== 'object' || Array.isArray(data)) throw new Error('Job must be an object');
            for (const name of ['placements', 'fiducials']) {
                if (!Array.isArray(data[name] ?? [])) throw new Error(`${name} must be an array`);
                for (const point of data[name] ?? []) {
                    if (!point || ![point.x, point.y, point.z].every(Number.isFinite)) {
                        throw new Error(`${name} require finite XYZ coordinates`);
                    }
                    for (const key of ['calX', 'calY', 'searchX', 'searchY']) {
                        if (point[key] != null && !Number.isFinite(point[key])) throw new Error(`${key} must be finite`);
                    }
                    if ((point.calX == null) !== (point.calY == null)) throw new Error('Calibrated XY must be a pair');
                }
            }
            for (const name of ['dispenseDegrees', 'retractionDegrees', 'dwellMilliseconds']) {
                if (data[name] != null && (!Number.isFinite(data[name]) || data[name] < 0)) {
                    throw new Error(`${name} must be finite and nonnegative`);
                }
            }
            for (const name of ['tipXoffset', 'tipYoffset']) {
                if (data[name] !== undefined && !Number.isFinite(data[name])) throw new Error(`${name} must be finite`);
            }
            for (const name of ['preGcode', 'postGcode']) {
                if (data[name] != null && typeof data[name] !== 'string') throw new Error(`${name} must be text`);
            }
            if (data.invertDispense != null && typeof data.invertDispense !== 'boolean') throw new Error('invertDispense must be boolean');
            if (data.coordinateFrame != null && !['machine', 'board'].includes(data.coordinateFrame)) throw new Error('Invalid coordinate frame');

            this.placements = (data.placements ?? []).map(p => {
                const point = new Point(p.x, p.y, p.z);
                point.calX = p.calX ?? null;
                point.calY = p.calY ?? null;
                return point;
            });
            this.fiducials = (data.fiducials ?? []).map(f => {
                const fid = new Fiducial(f.x, f.y, f.z, f.searchX, f.searchY);
                fid.calX = f.calX ?? null;
                fid.calY = f.calY ?? null;
                return fid;
            });
            // Saved registration is historical; the automation UI must explicitly
            // establish the current session's machine frame before planning motion.
            this.coordinateFrame = null;
            this.clickedFidBuffer = [];
            this.dispenseDegrees = data.dispenseDegrees ?? 30;
            this.retractionDegrees = data.retractionDegrees ?? 1;
            this.dwellMilliseconds = data.dwellMilliseconds ?? 100;
            this.preGcode = data.preGcode ?? '';
            this.postGcode = data.postGcode ?? '';
            this.invertDispense = data.invertDispense ?? false;
            if (data.tipXoffset !== undefined) this.lumen.tipXoffset = data.tipXoffset;
            if (data.tipYoffset !== undefined) this.lumen.tipYoffset = data.tipYoffset;

            // ui update
            const jobDispenseDeg = document.getElementById('jobDispenseDeg');
            const jobRetractionDeg = document.getElementById('jobRetractionDeg');
            const jobDwellMs = document.getElementById('jobDwellMs');
            const jobPreGcode = document.getElementById('jobPreGcode');
            const jobPostGcode = document.getElementById('jobPostGcode');
            const jobInvertDispense = document.getElementById('jobInvertDispense');

            if (jobDispenseDeg) jobDispenseDeg.value = this.dispenseDegrees;
            if (jobRetractionDeg) jobRetractionDeg.value = this.retractionDegrees;
            if (jobDwellMs) jobDwellMs.value = this.dwellMilliseconds;
            if (jobPreGcode) jobPreGcode.value = this.preGcode;
            if (jobPostGcode) jobPostGcode.value = this.postGcode;
            if (jobInvertDispense) jobInvertDispense.checked = this.invertDispense;

            // Update the UI position list
            this.loadJobIntoPositionList();

            this.drawJobToCanvas();

            return { success: true };
        } catch (error) {
            return { success: false, error: error.message || error.toString() };
        }
    }



    async saveToFile() {
        const jsonData = this.export();
        const blob = new Blob([jsonData], { type: 'application/json' });

        const handle = await window.showSaveFilePicker({
            suggestedName: 'job.json',
            types: [{
                description: 'JSON Files',
                accept: {
                    'application/json': ['.json']
                }
            }]
        });

        const writable = await handle.createWritable();
        await writable.write(blob);
        await writable.close();
    }

    createPositionElement(position, isFiducial) {
        const positionsList = document.querySelector('.positions-list');
        const newDiv = document.createElement('div');
        newDiv.className = 'position-item';

        let writtenX, writtenY;

        if(position.calX != null & position.calY != null){
            writtenX = position.calX;
            writtenY = position.calY;
        }
        else if(position.searchX != null & position.searchY != null){
            writtenX = position.searchX;
            writtenY = position.searchY;
        }
        else{
            writtenX = position.x;
            writtenY = position.y;
        }

        if(isFiducial){
            newDiv.innerHTML = `
            <span class="position-text">Fiducial: X:${writtenX} Y:${writtenY} Z:${position.z}</span>
            <div class="button-group">
                <button class="move-btn">☉</button>
                <button class="remove-btn">X</button>
            </div>
        `;
        }
        else{
            newDiv.innerHTML = `
            <span class="position-text">Position: X:${writtenX} Y:${writtenY} Z:${position.z}</span>
            <div class="button-group">
                <button class="move-btn">☉</button>
                <button class="remove-btn">X</button>
            </div>
        `;
        }



        // Add click handler for Move To button
        newDiv.querySelector('.move-btn').addEventListener('click', () => {

            let writtenX, writtenY;

            if(position.calX != null & position.calY != null){
                writtenX = position.calX;
                writtenY = position.calY;
            }
            else{
                writtenX = position.x;
                writtenY = position.y;
            }

            this.lumen.serial.send([
                "G90",  // Set absolute positioning
                "G0 Z31.5",
                `G0 X${writtenX} Y${writtenY}`  // Move to position
            ]);
        });

        // Add click handler for Remove button
        newDiv.querySelector('.remove-btn').addEventListener('click', () => {
            newDiv.remove();

            this.placements = this.placements.filter(p =>
                p.x !== position.x || p.y !== position.y || p.z !== position.z
            );

            this.fiducials = this.fiducials.filter(p =>
                p.x !== position.x || p.y !== position.y || p.z !== position.z
            );

            this.loadJobIntoPositionList();
            this.drawJobToCanvas();

            console.log(this.placements)
        });

        positionsList.appendChild(newDiv);
    }

    //TODO reimplement this
    // async capturePosition() {

    //     await this.capture();

    //     const lastPoint = this.getPoint(this.getPointCount() - 1);
    //     console.log('Last captured point:', lastPoint);

    //     if (lastPoint) {

    //         this.createPositionElement([lastPoint.x, lastPoint.y, lastPoint.z]);
    //     }
    // }

    // generates array of commands to send
    // in format serial.send(commands)
    slice(profile, options = {}) {
        return planJob(JSON.parse(this.export()), profile, options).commands;
    }

    async run() {
        throw new Error('Use the reviewed automation plan and runner');
    }


    export() {
        const data = {
            coordinateFrame: this.coordinateFrame,
            placements: this.placements.map(p => ({
                x: p.x,
                y: p.y,
                z: p.z,
                calX: p.calX,
                calY: p.calY,
                canvasX: p.canvasX,
                canvasY: p.canvasY
            })),
            fiducials: this.fiducials.map(f => ({
                x: f.x,
                y: f.y,
                z: f.z,
                calX: f.calX,
                calY: f.calY,
                canvasX: f.canvasX,
                canvasY: f.canvasY,
                searchX: f.searchX,
                searchY: f.searchY
            })),
            dispenseDegrees: this.dispenseDegrees,
            retractionDegrees: this.retractionDegrees,
            dwellMilliseconds: this.dwellMilliseconds,
            preGcode: this.preGcode,
            postGcode: this.postGcode,
            invertDispense: this.invertDispense,
            tipXoffset: this.lumen.tipXoffset,
            tipYoffset: this.lumen.tipYoffset
        };
        return JSON.stringify(data, null, 2);
    }

    // performs a linear transformation on all placement points based on three fiducial points
    // realFids should be an array of three [x,y] coordinates representing where the fiducials actually are
    transformPlacements(realFids) {
        const origFids = this.fiducials.map(f => [f.x, f.y]);
        validateTriangle(origFids, 'Source registration');
        validateTriangle(realFids, 'Machine registration');
        if (this.placements.some(p => ![p.x, p.y].every(Number.isFinite))) {
            throw new Error('Placements require finite XY coordinates');
        }
        const matrix = fromTriangles(origFids, realFids);
        const transformed = this.placements.map(point => applyToPoint(matrix, [point.x, point.y]));
        if (transformed.some(point => !point.every(Number.isFinite))) throw new Error('Invalid registration transform');
        this.placements.forEach((point, i) => {
            [point.calX, point.calY] = transformed[i];
        });
    }

}