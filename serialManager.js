export class serialManager {
    constructor(modal, { ackTimeoutMs = 5000, maxCommandMs = 120000 } = {}) {
        if (![ackTimeoutMs, maxCommandMs].every(value => Number.isFinite(value) && value > 0)) {
            throw new Error("Serial deadlines must be finite positive milliseconds.");
        }
        this.encoder = new TextEncoder();
        this.decoder = new TextDecoder();
        this.consoleDiv = globalThis.document?.getElementById("console");
        this.port;
        this.shouldListen = true;

        this.modal = modal;

        this.receiveBuffer = [];
        this.inspectBuffer = [];

        this.sentCommandBuffer = [""];
        this.sentCommandBufferIndex = 0;

        this.okRespTimeout = false;
        this.timeoutID = undefined;

        this.ackTimeoutMs = ackTimeoutMs;
        this.maxCommandMs = maxCommandMs;
        this.sending = false;
        this.fault = null;
        this.pending = null;
        this.reader = null;
        this.listenTask = null;
        this.disconnectHandler = () => {
            if (!this.port?.readable || !this.port?.writable) {
                this.fail(new Error("Serial device disconnected. Reconnect before sending."));
            }
        };

        this.bootCommands = ["M115", "M114"];

    }


    async appendToConsole(message, direction){
        if (!this.consoleDiv) return;
        let newConsoleEntry = document.createElement('p')
        let timestamp = new Date().toISOString();
        let dir = "";

        if(direction){
        dir = "[SEND]"
        }
        else{
        dir = "[RECE]"
        }
        
        newConsoleEntry.textContent = dir + " - " + timestamp + " - " + message + '\n';
        this.consoleDiv.appendChild(newConsoleEntry)
        
        this.consoleDiv.scrollTop = this.consoleDiv.scrollHeight;
    }

    clearBuffer(){
        while(this.receiveBuffer.length > 0){
            this.receiveBuffer.shift();
        }
    }

    clearInspectBuffer(){
        while(this.inspectBuffer.length > 0){
            this.inspectBuffer.shift();
        }
    }

    dec2bin(dec) {
        return (dec >>> 0).toString(2);
    }

    delay = (delayInms) => {
        return new Promise(resolve => setTimeout(resolve, delayInms));
    };
    
    

    async connect() {
        if (!navigator.serial){
            this.modal.show("Browser Support", "Please use a browser that supports WebSerial, like Chrome, Opera, or Edge. <a href='https://developer.mozilla.org/en-US/docs/Web/API/Web_Serial_API#browser_compatibility'>Supported Browsers.");
            return false
        }

        if (this.sending) throw new Error("Cannot connect during a serial command batch.");
        if (this.port) await this.disconnect();

        const usbVendorId = 0x0483;
        this.port = await navigator.serial.requestPort({ filters: [{ usbVendorId }] })    
        console.log("Port Selected.")

        await this.port.open({
        baudRate: 115200,
        bufferSize: 255,
        dataBits: 8,
        flowControl: "none",
        parity: "none",
        stopBits: 1
        })

        console.log("Port Opened.")
        // const { clearToSend, dataCarrierDetect, dataSetReady, ringIndicator} = await this.port.getSignals()
        // console.log({ clearToSend, dataCarrierDetect, dataSetReady, ringIndicator})
        this.shouldListen = true;
        this.fault = null;
        this.decoder = new TextDecoder();
        this.clearBuffer();
        this.clearInspectBuffer();
        navigator.serial.addEventListener?.("disconnect", this.disconnectHandler);
        this.listenTask = this.listen();
        // Initialization must be serialized and acknowledged before reporting ready.
        await this.send(this.bootCommands);
        const button = document.querySelector("#connect");
        if (button) {
            button.style.background = 'green';
            button.style.color = 'white';
            button.textContent = 'Connected';
        }
        return true;
    }

    fail(error) {
        this.fault ??= error;
        this.pending?.reject(this.fault);
    }

    receiveLine(rawLine) {
        const line = rawLine.trim();
        if (!line) return;
        this.receiveBuffer.push(line);
        this.inspectBuffer.push(line);
        // Keep long-running sessions bounded while preserving diagnostic replies.
        if (this.receiveBuffer.length > 10000) this.receiveBuffer.shift();
        if (this.inspectBuffer.length > 10000) this.inspectBuffer.shift();
        this.appendToConsole(line, false);
        if (/^start$/i.test(line)) {
            this.fail(new Error("Firmware restarted; machine state is unknown. Reconnect before sending."));
        } else if (/^(?:error\s*:|!!|resend\s*:|rs\s)|^echo:.*(?:unknown command|halted|kill\(\))/i.test(line)) {
            this.fail(new Error(`Firmware rejected command: ${line}. Reconnect before sending.`));
        } else if (/^ok(?:\s|$)/i.test(line)) {
            this.pending?.resolve();
        } else if (/^(?:echo:)?busy:\s*processing$/i.test(line)) {
            this.pending?.refresh();
        }
    }

    async listen() {
        let partial = "";
        const reader = this.port.readable.getReader();
        this.reader = reader;
        try {
            while (this.shouldListen) {
                const { value, done } = await reader.read();
                if (done) throw new Error("Serial device disconnected. Reconnect before sending.");
                partial += this.decoder.decode(value, { stream: true });
                let newline;
                while ((newline = partial.indexOf("\n")) !== -1) {
                    this.receiveLine(partial.slice(0, newline));
                    partial = partial.slice(newline + 1);
                }
                if (partial.length > 65536) throw new Error("Serial response exceeds line limit.");
            }
        } catch (error) {
            this.fail(error);
        } finally {
            reader.releaseLock();
            if (this.reader === reader) this.reader = null;
        }
    }

    async disconnect() {
        this.shouldListen = false;
        this.fail(new Error("Serial device disconnected. Reconnect before sending."));
        navigator.serial?.removeEventListener?.("disconnect", this.disconnectHandler);
        await this.reader?.cancel();
        await this.listenTask;
        // A pending write may keep the stream locked; never pretend it closed.
        await this.port?.close();
        this.port = undefined;
    }

    async send(commandArray) {
        if (!Array.isArray(commandArray) || commandArray.some(command =>
            typeof command !== "string" || !command.trim() || /[\r\n\0]/.test(command))) {
            throw new Error("Commands must be an array of nonempty single-line strings.");
        }
        if (this.fault) throw this.fault;
        if (this.sending) throw new Error("A serial command batch is already running.");
        if (!this.port?.writable) throw new Error("Cannot write: connect the serial port first.");
        this.sending = true;
        let writer;
        try {
            writer = this.port.writable.getWriter();
            for (const command of commandArray) {
                if (this.fault) throw this.fault;
                // Arm the acknowledgement before write: firmware can answer immediately.
                this.clearBuffer();
                let idleTimer, totalTimer;
                let settled = false;
                let rejectFailure;
                const failure = new Promise((_, reject) => { rejectFailure = reject; });
                const response = new Promise((resolve, reject) => {
                    const timeout = () => {
                        this.okRespTimeout = true;
                        this.fail(new Error(`Timed out waiting for acknowledgement: ${command}. Reconnect before sending.`));
                    };
                    const finish = callback => value => {
                        if (settled) return;
                        settled = true;
                        clearTimeout(idleTimer);
                        // Keep the hard deadline active until writer.write also completes.
                        callback(value);
                    };
                    const refresh = () => {
                        if (!settled) {
                            clearTimeout(idleTimer);
                            idleTimer = setTimeout(timeout, this.ackTimeoutMs);
                        }
                    };
                    this.pending = {
                        resolve: finish(resolve),
                        reject: error => { finish(reject)(error); rejectFailure(error); },
                        refresh
                    };
                    refresh();
                });
                const deadline = new Promise((_, reject) => {
                    totalTimer = setTimeout(() => {
                        const error = new Error(`Command deadline exceeded: ${command}. Reconnect before sending.`);
                        this.fail(error);
                        reject(error);
                    }, this.maxCommandMs);
                });
                try {
                    this.okRespTimeout = false;
                    this.appendToConsole(command, true);
                    await Promise.race([
                        Promise.all([writer.write(this.encoder.encode(command + "\n")), response]),
                        deadline, failure
                    ]);
                    if (this.fault) throw this.fault;
                } finally {
                    clearTimeout(idleTimer);
                    clearTimeout(totalTimer);
                    this.pending = null;
                }
            }
        } catch (error) {
            this.fail(error);
            throw error;
        } finally {
            try { writer?.releaseLock(); } finally { this.sending = false; }
        }
    }

    async sendRepl() {
        let command = [document.querySelector("#repl-input").value];

        //adding current command to buffer for uparrow access later, at position 1 to preserve a "" option
        this.sentCommandBuffer.splice(1, 0, command[0])

        //making sure we reset the index back to 0
        this.sentCommandBufferIndex = 0;
        
        return this.send(command);

    }


    // TODO most of everything beneath here should move to lumen, not serial

    async leftAirOn(){
        const commandArray = [
        "M106",
        "M106 P1 S255"
        ]
        await this.send(commandArray);
    }

    async leftAirOff(){
        const commandArray = [
        "M107",
        "M107 P1"
        ]
        await this.send(commandArray);
    }

    async rightAirOn(){
        const commandArray = [
        "M106 P2 S255",
        "M106 P3 S255"
        ]
        await this.send(commandArray);
    }

    async rightAirOff(){
        const commandArray = [
        "M107 P2",
        "M107 P3"
        ]
        await this.send(commandArray);
    }

    async ledOn(){
        const commandArray = [
        "M150 P255 R255 U255 B255"
        ]

        await this.send(commandArray);
    }

    async ledOff(){
        const commandArray = [
        "M150 P0"
        ]
        await this.send(commandArray);
    }

    async disableSteppers(){
        const commandArray = [
            "M18"
            ]
            await this.send(commandArray);
    }

    async readLeftVac(){

        if(!this.port?.writable){
        this.modal.show("Cannot Write", "Cannot write to port. Have you connected?");
        return false
        }

        const commandArrayLeft = [
        "M260 A112 B1 S1"
        ]

        const delayVal = 50;

        this.clearInspectBuffer();

        let msb, csb, lsb;
        const regex = new RegExp('data:(..)');

        //send command array
        await this.send(commandArrayLeft);

        this.clearInspectBuffer();

        await this.send(["M260 A109 B6 S1"]);
        await this.send(["M261 A109 B1 S1"]);

        await this.delay(delayVal);

        for (var i=0, x=this.inspectBuffer.length; i<x; i++) {
            let currLine = this.inspectBuffer[i];
            console.log(this.inspectBuffer)
            let result = regex.test(currLine);
            if(result){
                msb = currLine.match("data:(..)")[1];
                break
            }
        }

        this.clearInspectBuffer();
        
        await this.send(["M260 A109 B7 S1"]);
        await this.send(["M261 A109 B1 S1"]);

        await this.delay(delayVal);

        for (var i=0, x=this.inspectBuffer.length; i<x; i++) {
            let currLine = this.inspectBuffer[i];
            let result = regex.test(currLine);
            if(result){
                csb = currLine.match("data:(..)")[1];
                break
            }
        }

        this.clearInspectBuffer();
        
        await this.send(["M260 A109 B8 S1"]);
        await this.send(["M261 A109 B1 S1"]);

        await this.delay(delayVal);

        for (var i=0, x=this.inspectBuffer.length; i<x; i++) {
            let currLine = this.inspectBuffer[i];
            let result = regex.test(currLine);
            if(result){
                lsb = currLine.match("data:(..)")[1];
                break
            }
        }

        // convert hex string to int
        //msb = parseInt(msb, 16);

        // get biggest bit to determine sign
        //let readingSign = (msb & (1 << 7)) === 0 ? 1 : -1;

        // clear biggest bit for actual value calc
        //msb &= 0x7F;

        console.log(msb, csb, lsb)

        let result = parseInt(msb+csb+lsb, 16);

        if(result & (1 << 23)){
            result = result - 2**24
        }

        

        let resp = await this.modal.show("Left Vacuum Sensor Value", result);

        this.clearInspectBuffer();      

    }

    async readRightVac(){

        if(!this.port?.writable){
            this.modal.show("Cannot Write", "Cannot write to port. Have you connected?");
        return false
        }

        const commandArrayRight = [
        "M260 A112 B2 S1",
        ]

        let msb, csb, lsb;
        const regex = new RegExp('data:(..)');

        const delayVal = 50;

        this.clearInspectBuffer();

        //send command array
        await this.send(commandArrayRight);
        await this.delay(delayVal);

        this.clearInspectBuffer();

        await this.send(["M260 A109 B6 S1"]);
        await this.send(["M261 A109 B1 S1"]);
        await this.delay(delayVal);

        for (var i=0, x=this.inspectBuffer.length; i<x; i++) {
            let currLine = this.inspectBuffer[i];
            let result = regex.test(currLine);
            if(result){
                msb = currLine.match("data:(..)")[1];
                break
            }
        }

        this.clearInspectBuffer();
        
        await this.send(["M260 A109 B7 S1"]);
        await this.send(["M261 A109 B1 S1"]);
        await this.delay(delayVal);

        for (var i=0, x=this.inspectBuffer.length; i<x; i++) {
            let currLine = this.inspectBuffer[i];
            let result = regex.test(currLine);
            if(result){
                csb = currLine.match("data:(..)")[1];
                break
            }
        }

        this.clearInspectBuffer();
        
        await this.send(["M260 A109 B8 S1"]);
        await this.send(["M261 A109 B1 S1"]);
        await this.delay(delayVal);

        for (var i=0, x=this.inspectBuffer.length; i<x; i++) {
            let currLine = this.inspectBuffer[i];
            let result = regex.test(currLine);
            if(result){
                lsb = currLine.match("data:(..)")[1];
                break
            }
        }

        // // convert hex string to int
        // msb = parseInt(msb, 16);

        // // get biggest bit to determine sign
        // let readingSign = (msb & (1 << 7)) === 0 ? 1 : -1;

        // // clear biggest bit for actual value calc
        // msb &= 0x7F;

        // let rightVal = parseInt(msb.toString(16)+csb+lsb, 16) * readingSign;

        let result = parseInt(msb+csb+lsb, 16);

        if(result & (1 << 23)){
            result = result - 2**24
        }

        await this.modal.show("Right Vacuum Sensor Value", result);

        this.clearInspectBuffer();

    }

    // tests

    async testTMC(){

        if(!this.port?.writable){
            this.modal.show("Cannot Write", "Cannot write to port. Have you connected?");
        return false
        }

        let testDataBuffer = "";

        const commandArray = [
            "M122"
        ]

        //clean out receive buffer
        await this.clearBuffer();
        
        //send command array
        await this.send(commandArray);

        await this.delay(5000);

        //check receieve buffer
        console.log(this.receiveBuffer);

        //adding to test buffer
        for(let i = 0; i<this.receiveBuffer.length; i++){
            testDataBuffer = testDataBuffer.concat(this.receiveBuffer[i] + "\n");
        }

        let resp = await this.modal.show("Stepper Driver Test Complete", "Test is complete. Click OK to download test report.");

        if(resp == true){
            let filename = new Date().toISOString();
            filename = filename + "-tmctest.txt"

            this.download(filename, testDataBuffer);
        }


    }

    async testVac(){

        if(!this.port?.writable){
            this.modal.show("Cannot Write", "Cannot write to port. Have you connected?");
        return false
        }

        let testDataBuffer = "";

        const commandArrayLeft = [
        "M260 A112 B1 S1",
        "M260 A109",
        "M260 B48",
        "M260 B10",
        "M260 S1"
        ]

        const commandArrayRight = [
        "M260 A112 B2 S1",
        "M260 A109",
        "M260 B48",
        "M260 B10",
        "M260 S1"
        ]

        const delayVal = 100;

        this.clearBuffer();

        let msb, csb, lsb;
        const regex = new RegExp('data:(..)');

        //send command array
        await this.send(commandArrayLeft);

        await this.send(["M260 A109 B6 S1"]);
        await this.send(["M261 A109 B1 S1"]);
        await this.delay(delayVal);

        for (var i=0, x=this.receiveBuffer.length; i<x; i++) {
        let currLine = this.receiveBuffer[i];
        let result = regex.test(currLine);
        if(result){
            msb = currLine.match("data:(..)")[1];
            testDataBuffer = testDataBuffer.concat("Left MSB - " + msb + "\n");
            break
        }
        }

        this.clearBuffer();
        
        await this.send(["M260 A109 B7 S1"]);
        await this.send(["M261 A109 B1 S1"]);
        await this.delay(delayVal);

        for (var i=0, x=this.receiveBuffer.length; i<x; i++) {
        let currLine = this.receiveBuffer[i];
        let result = regex.test(currLine);
        if(result){
            csb = currLine.match("data:(..)")[1];
            testDataBuffer = testDataBuffer.concat("Left CSB - " + csb + "\n");
            break
        }
        }

        this.clearBuffer();
        
        await this.send(["M260 A109 B8 S1"]);
        await this.send(["M261 A109 B1 S1"]);
        await this.delay(delayVal);

        for (var i=0, x=this.receiveBuffer.length; i<x; i++) {
        let currLine = this.receiveBuffer[i];
        let result = regex.test(currLine);
        if(result){
            lsb = currLine.match("data:(..)")[1];
            testDataBuffer = testDataBuffer.concat("Left LSB - " + lsb + "\n");
            break
        }
        }

        let leftVal = parseInt(msb+csb+lsb, 16);

        if(leftVal & (1 << 23)){
            leftVal = leftVal - 2**24
        }

        testDataBuffer = testDataBuffer.concat("Left Val - " + leftVal + "\n");

        // NOW RIGHT SENSOR

        this.clearBuffer();

        //send command array
        await this.send(commandArrayRight);

        await this.send(["M260 A109 B6 S1"]);
        await this.send(["M261 A109 B1 S1"]);
        await this.delay(delayVal);

        for (var i=0, x=this.receiveBuffer.length; i<x; i++) {
        let currLine = this.receiveBuffer[i];
        let result = regex.test(currLine);
        if(result){
            msb = currLine.match("data:(..)")[1];
            testDataBuffer = testDataBuffer.concat("Right MSB - " + msb + "\n");
            break
        }
        }

        this.clearBuffer();
        
        await this.send(["M260 A109 B7 S1"]);
        await this.send(["M261 A109 B1 S1"]);
        await this.delay(delayVal);

        for (var i=0, x=this.receiveBuffer.length; i<x; i++) {
        let currLine = this.receiveBuffer[i];
        let result = regex.test(currLine);
        if(result){
            csb = currLine.match("data:(..)")[1];
            testDataBuffer = testDataBuffer.concat("Right CSB - " + csb + "\n");
            break
        }
        }

        this.clearBuffer();
        
        await this.send(["M260 A109 B8 S1"]);
        await this.send(["M261 A109 B1 S1"]);
        await this.delay(delayVal);

        console.log("current buffer length: ", this.receiveBuffer.length)
        for (var i=0, x=this.receiveBuffer.length; i<x; i++) {
        let currLine = this.receiveBuffer[i];
        let result = regex.test(currLine);
        if(result){
            lsb = currLine.match("data:(..)")[1];
            testDataBuffer = testDataBuffer.concat("Right LSB - " + lsb + "\n");
            break
        }
        }

        let rightVal = parseInt(msb+csb+lsb, 16);

        if(rightVal & (1 << 23)){
            rightVal = rightVal - 2**24
        }

        testDataBuffer = testDataBuffer.concat("Right Val - " + rightVal + "\n");

        console.log(leftVal, rightVal)

        let resp = await this.modal.show("Vacuum Sensor Test Complete", "Test is complete. Click OK to download test report.");

        if(resp == true){
            let filename = new Date().toISOString();
            filename = filename + "-vactest.txt"
            this.download(filename, testDataBuffer);
        }

    }

    download(filename, text) {
        var element = document.createElement('a');
        element.setAttribute('href', 'data:text/plain;charset=utf-8,' + encodeURIComponent(text));
        element.setAttribute('download', filename);

        element.style.display = 'none';
        document.body.appendChild(element);

        element.click();

        document.body.removeChild(element);
    }

    async goToRelative(x, y){
        await this.send([
            "G91",  // Set relative positioning
            `G0 X${x} Y${y}`,  // Move relative to current position
            "G90"   // Set absolute positioning
          ]);
    }

    async goTo(x, y){
        await this.send([
            `G0 X${x} Y${y}`, 
          ]);
    }
  
  }