// Operator-driven paste experiments. Opening this window performs no motion.
(function () {
    var J = Java.type, Swing = J('javax.swing.SwingUtilities'), F = J('java.io.File');
    var Files = J('java.nio.file.Files'), UTF = J('java.nio.charset.StandardCharsets').UTF_8;
    var root = String(java.lang.System.getenv('LUMEN_AUTOMATION_ROOT') || (java.lang.System.getProperty('user.home') + '/lumenpnp'));
    function read(path) { return String(new java.lang.String(Files.readAllBytes(new F(path).toPath()), UTF)); }
    var profile = JSON.parse(read(root + '/automation/plans/paste-operator-profile.json'));
    eval(read(root + '/automation/paste/native-air.cjs'));
    eval(read(root + '/automation/paste/connection-policy.cjs'));
    eval(read(root + '/automation/paste/waste-prime.cjs'));
    eval(read(root + '/automation/paste/operator-console-policy.cjs'));
    eval(read(root + '/automation/paste/operator-console-native.js'));
    Swing.invokeLater(new (J('java.lang.Runnable'))({run: function () {
        var retained={};
        function retainControls(component){var labels={doseDegrees:'Dose per pad',retractPercent:'Retraction between',dwellMs:'Wait after each dose',retractDwellMs:'Wait after retraction',bSpeedFraction:'Extrusion motor speed',workZ:'Raw work Z',gapMm:'Commanded gap'};if(component instanceof J('javax.swing.JPanel')){var cs=component.getComponents();if(cs.length>=2&&cs[0] instanceof J('javax.swing.JLabel')){var label=String(cs[0].getText());Object.keys(labels).forEach(function(k){if(label.indexOf(labels[k])===0&&cs[1] instanceof J('javax.swing.JSpinner'))retained[k]=Number(cs[1].getValue());});if(label.indexOf('Height mode:')===0&&cs[1] instanceof J('javax.swing.JComboBox'))retained.heightMode=String(cs[1].getSelectedItem());}}if(component instanceof J('java.awt.Container'))for each(var child in component.getComponents())retainControls(child);}
        // One console at a time; never replace an active operator task.
        for each(var old in J('java.awt.Window').getWindows()) {
            if(old instanceof J('javax.swing.JFrame') && old.isVisible() && String(old.getTitle()).indexOf('Paste experiments')===0){
                if(J('org.openpnp.model.Configuration').get().getMachine().isBusy())throw Error('Wait for the active task before reopening the console');
                retainControls(old.getContentPane());old.dispatchEvent(new (J('java.awt.event.WindowEvent'))(old,J('java.awt.event.WindowEvent').WINDOW_CLOSING));
            }
        }
        var frame = new (J('javax.swing.JFrame'))('Paste experiments — ' + (profile.name || 'registered board'));
        var panel = new (J('javax.swing.JPanel'))(new (J('java.awt.BorderLayout'))(8, 8));
        panel.setBorder(J('javax.swing.BorderFactory').createEmptyBorder(12, 12, 12, 12));
        var model = new (J('javax.swing.DefaultListModel'))();
        var refs = Object.keys(profile.pads).sort(function(a,b){return Number(a.slice(1))-Number(b.slice(1));});
        refs.forEach(function(ref){model.addElement(ref);});
        var list = new (J('javax.swing.JList'))(model);
        list.setSelectionMode(J('javax.swing.ListSelectionModel').MULTIPLE_INTERVAL_SELECTION);
        list.setSelectedIndex(0); list.setVisibleRowCount(16);
        var left = new (J('javax.swing.JPanel'))(new (J('java.awt.BorderLayout'))(4,4));
        left.add(new (J('javax.swing.JLabel'))('Resistors (Ctrl/Shift selects a group)'), 'North');
        left.add(new (J('javax.swing.JScrollPane'))(list), 'Center');
        panel.add(left, 'West');
        var controls = new (J('javax.swing.JPanel'))();
        controls.setLayout(new (J('javax.swing.BoxLayout'))(controls, J('javax.swing.BoxLayout').Y_AXIS));
        var fields = {}, buttons = [], dispenseButtons = [], idleButtons = [], armed = false, busy = false, lastPadMode = 'both', api=null, lastError='';
        var stateLabel = new (J('javax.swing.JLabel'))('DISARMED — check supervision, then Connect/check controller');
        controls.add(stateLabel);
        var calibrationLabel=new (J('javax.swing.JLabel'))('XY: none | Z: none');controls.add(calibrationLabel);
        var log = new (J('javax.swing.JTextArea'))(9,70); log.setEditable(false); log.setLineWrap(true); log.setWrapStyleWord(true);
        function note(s){log.append(String(s)+'\n');log.setCaretPosition(log.getDocument().getLength());}
        function row(label, component){var p=new (J('javax.swing.JPanel'))(new (J('java.awt.FlowLayout'))(J('java.awt.FlowLayout').LEFT));p.add(new (J('javax.swing.JLabel'))(label));p.add(component);controls.add(p);return p;}
        function number(key,label,value,min,max,step){if(typeof retained[key]==='number'&&isFinite(retained[key]))value=Math.max(min,Math.min(max,retained[key]));var spinner=new (J('javax.swing.JSpinner'))(new (J('javax.swing.SpinnerNumberModel'))(new java.lang.Double(value),new java.lang.Double(min),new java.lang.Double(max),new java.lang.Double(step)));fields[key]=spinner;row(label,spinner);}
        number('doseDegrees','Dose per pad (motor degrees)',6,0.25,30,0.25);
        number('retractPercent','Retraction between resistors (%)',15,0,50,5);
        number('dwellMs','Wait after each dose (ms)',2000,0,5000,100);
        number('retractDwellMs','Wait after retraction (ms)',500,0,2000,100);
        number('bSpeedFraction','Extrusion motor speed (fraction)',0.05,0.01,1,0.01);
        number('workZ','Raw work Z — larger = lower (mm)',profile.workZ,55,profile.workZ,0.05);
        var heightMode=new (J('javax.swing.JComboBox'))(Java.to(['gap','raw'],'java.lang.String[]'));heightMode.setSelectedItem(retained.heightMode|| (profile.vacuumReference?'gap':'raw'));row('Height mode: gap above touch / raw Z',heightMode);
        number('gapMm','Commanded gap above needle touch (mm)',.20,.15,1,.05);
        var touchButton=null,threeTouchButton=null,touchApproachLabel=null,touchLoaded=false;
        controls.add(new (J('javax.swing.JLabel'))('XY/Z travel stays at 100%. No retraction between the two pads.'));
        controls.add(new (J('javax.swing.JLabel'))('Gap mode follows measured needle touch plus relative board slope; it is not precision gap metrology.'));
        var confirm=new (J('javax.swing.JCheckBox'))('I am watching; board is secured, selected pads usable, and motion area is clear.');
        controls.add(confirm);
        function selected(){var a=[],values=list.getSelectedValuesList();for(var i=0;i<values.size();i++)a.push(String(values.get(i)));if(!a.length)throw Error('Select at least one resistor');return a;}
        function recipe(){if(busy)throw Error('Wait for the current run to finish');var r={};Object.keys(fields).forEach(function(k){fields[k].commitEdit();r[k]=Number(fields[k].getValue());});r.heightMode=String(heightMode.getSelectedItem());return r;}
        function update(){
            var c=api?api.calibrationStatus():{ready:false};var chosen=String(list.getSelectedValue()||''),canRecordTouch=!!(c.lastApproach&&c.lastApproach.ref===chosen&&c.lastApproach.pad==='1');if(touchApproachLabel)touchApproachLabel.setText(canRecordTouch?'Needle approach matches '+chosen+' Pad 1; confirm actual metal contact before recording':'Touch recording locked: use NEEDLE Approach Pad 1 first; Camera buttons move only the camera.');
            calibrationLabel.setText((c.alignmentApplied?'XY ready':'XY required')+' | '+(c.needleTouchRecorded?'Needle touch recorded — gap is commanded above this zero':c.vacuumReferenceAvailable?'Relative vacuum plane ready — NEEDLE TOUCH REQUIRED':('Touch references: '+(c.touchReferences||[]).join(', ')+' | measured gaps: '+(c.zReferences||[]).join(', ')+'; '+(c.zApplied?'Z ready':'Z required'))));
            if(c.needleTouchRecorded&&!touchLoaded){touchLoaded=true;heightMode.setSelectedItem('gap');if(c.commandedGapMm!==undefined&&c.commandedGapMm!==null)fields.gapMm.setValue(new java.lang.Double(c.commandedGapMm));touchLoaded=true;}if(!c.needleTouchRecorded)touchLoaded=false;
            if(c.workZ!==undefined&&fields.workZ){fields.workZ.getModel().setMaximum(new java.lang.Double(c.workZ));if(Number(fields.workZ.getValue())>c.workZ)fields.workZ.setValue(new java.lang.Double(c.workZ));}
            buttons.forEach(function(b){b.setEnabled(armed&&!busy);});
            dispenseButtons.forEach(function(b){b.setEnabled(armed&&!busy&&c.ready===true);});
            idleButtons.forEach(function(b){b.setEnabled(!busy);});
            Object.keys(fields).forEach(function(k){fields[k].setEnabled(!busy);});heightMode.setEnabled(!busy);fields.workZ.setEnabled(!busy&&String(heightMode.getSelectedItem())==='raw');fields.gapMm.setEnabled(!busy&&String(heightMode.getSelectedItem())==='gap');if(touchButton)touchButton.setEnabled(armed&&!busy&&canRecordTouch&&c.vacuumReferenceAvailable===true);if(threeTouchButton)threeTouchButton.setEnabled(armed&&!busy&&canRecordTouch);list.setEnabled(!busy);confirm.setEnabled(!busy);
            stateLabel.setText(lastError?'ERROR — '+lastError:(busy?'BUSY — completing controller action':(!armed?'DISARMED — check supervision, then Connect/check controller':(c.ready?'READY — alignment and height recorded':'CALIBRATION REQUIRED — camera controls available; dispense locked'))));
        }
        list.addListSelectionListener(new (J('javax.swing.event.ListSelectionListener'))({valueChanged:function(){if(api)update();}}));
        heightMode.addActionListener(new (J('java.awt.event.ActionListener'))({actionPerformed:function(){update();}}));
        api=PasteOperator.create(profile,function(event){Swing.invokeLater(new (J('java.lang.Runnable'))({run:function(){if(event.busy!==undefined)busy=!!event.busy;if(event.armed!==undefined){armed=!!event.armed;if(armed)lastError='';}if(event.error){armed=false;lastError=String(event.error);note('STOPPED: '+event.error);}if(event.message)note(event.message);if(event.message==='completed-awaiting-operator-inspection')note('Controller operation completed and verified. Recorded calibration references are shown above.');if(event.record)note('Saved: '+event.record);update();}}));});
        function call(fn){try{fn();}catch(e){note('Not run: '+e);}}
        confirm.addActionListener(new (J('java.awt.event.ActionListener'))({actionPerformed:function(){call(function(){if(!confirm.isSelected()){api.disarm();armed=false;}update();});}}));
        function button(parent,label,fn,motion){var b=new (J('javax.swing.JButton'))(label);b.addActionListener(new (J('java.awt.event.ActionListener'))({actionPerformed:function(){call(fn);}}));parent.add(b);if(motion==='dispense')dispenseButtons.push(b);else if(motion)buttons.push(b);else idleButtons.push(b);return b;}
        var connection=row('1. Controller',new (J('javax.swing.JLabel'))(''));
        button(connection,'Connect/check controller',function(){if(!confirm.isSelected())throw Error('First check the supervision / clear-area checkbox');api.arm();note('Checking existing OpenPnP connection; no motion…');},false);
        button(connection,'Board replaced / Reset calibration',function(){api.invalidateCalibration();note('Previous alignment and height invalidated. Recheck R1, R15 and R40.');update();},false);
        var nav=row('CAMERA ONLY — does not position the needle',new (J('javax.swing.JLabel'))('Selected resistor:'));
        ['1','2','center'].forEach(function(p){button(nav,p==='center'?'Center':'Pad '+p,function(){api.jump(selected()[0],p);},true);});
        var jogStep=new (J('javax.swing.JSpinner'))(new (J('javax.swing.SpinnerNumberModel'))(new java.lang.Double(.1),new java.lang.Double(.01),new java.lang.Double(1),new java.lang.Double(.05)));
        var jog=row('2. Align camera (mm)',jogStep);
        [['X −',-1,0],['X +',1,0],['Y −',0,-1],['Y +',0,1]].forEach(function(a){button(jog,a[0],function(){jogStep.commitEdit();var step=Number(jogStep.getValue());api.jogCamera(a[1]*step,a[2]*step);},true);});
        var align=row('R1 → R15 → R40',new (J('javax.swing.JLabel'))('Center between both copper pads, then:'));
        button(align,'Record aligned center',function(){api.recordAlignment(selected()[0]);note('Alignment capture requested for '+selected()[0]);update();},true);
        button(align,'Apply 3-point XY',function(){api.applyAlignment();note('Three-point board alignment applied locally. Now check height.');update();},true);
        var checkZ=new (J('javax.swing.JSpinner'))(new (J('javax.swing.SpinnerNumberModel'))(new java.lang.Double(55),new java.lang.Double(55),new java.lang.Double(profile.calibrationRawZMax===undefined?profile.workZ:profile.calibrationRawZMax),new java.lang.Double(.05)));
        var height=row('3. Needle calibration raw Z (starts high at 55)',checkZ);
        button(height,'NEEDLE: approach selected Pad 1 (no paste)',function(){checkZ.commitEdit();api.approach(selected()[0],'1',Number(checkZ.getValue()));},true);
        button(height,'Lift both heads to clearance',function(){api.lift();},true);
        touchApproachLabel=new (J('javax.swing.JLabel'))('Use NEEDLE Approach before recording touch.');controls.add(touchApproachLabel);
        var touchRow=row('Single needle touch-off (after relative vacuum plane)',new (J('javax.swing.JLabel'))(''));
        touchButton=button(touchRow,'Record needle barely touching Pad 1',function(){
            var c=api.calibrationStatus();if(!c.vacuumReferenceAvailable)throw Error('Fresh relative vacuum-plane reference required');
            fields.gapMm.commitEdit();var desired=Number(fields.gapMm.getValue());
            var answer=J('javax.swing.JOptionPane').showConfirmDialog(frame,'Confirm the METAL needle is barely touching selected '+selected()[0]+' Pad 1 now.\nThis records the current height as zero; it does not lower the needle.\nThen Lift; dispensing uses '+desired+' mm commanded above this zero.','Record physical needle touch',J('javax.swing.JOptionPane').YES_NO_OPTION);
            if(answer!==J('javax.swing.JOptionPane').YES_OPTION)return;
            api.recordNeedleTouch(selected()[0],'1',desired);heightMode.setSelectedItem('gap');note('Operator needle-touch capture requested. Lift to clearance before dispensing.');
        },true);
        controls.add(new (J('javax.swing.JLabel'))('Vacuum provides relative board slope only. The explicit metal-needle touch establishes the working zero.'));
        var threeTouch=row('No gauge needed: touch R1 → R15 → R40 Pad 1',new (J('javax.swing.JLabel'))(''));
        threeTouchButton=button(threeTouch,'Record bare-needle touch at selected reference',function(){
            var answer=J('javax.swing.JOptionPane').showConfirmDialog(frame,'Confirm the bare METAL needle is barely touching '+selected()[0]+' Pad 1 now. This records the current height; it does not move.','Record one of three needle touches',J('javax.swing.JOptionPane').YES_NO_OPTION);
            if(answer!==J('javax.swing.JOptionPane').YES_OPTION)return;
            api.recordNeedleTouchPoint(selected()[0],'1');note('Needle-touch capture requested for '+selected()[0]+'. Wait for verified completion and the recorded-reference list to update.');
        },true);
        button(threeTouch,'Apply 3 needle touches',function(){fields.gapMm.commitEdit();api.applyNeedleTouches(Number(fields.gapMm.getValue()));heightMode.setSelectedItem('gap');note('Three confirmed needle touches applied. Gap is commanded above the touch plane; Lift, then dispense.');update();},true);
        controls.add(new (J('javax.swing.JLabel'))('After board reset: align XY, record three bare-needle touches, Apply 3 touches, Lift. No vacuum plane or gauge required.'));
        var gap=new (J('javax.swing.JTextField'))(6);gap.setToolTipText('Enter a physically measured gap from 0.1 to 3 mm; no assumed default.');
        var zrecord=row('Measured needle-to-board gap (mm)',gap);
        button(zrecord,'Record measured gap',function(){var entered=String(gap.getText()).trim();if(!entered)throw Error('Enter the gap you physically measured at this position');api.recordZ(selected()[0],Number(entered));gap.setText('');note('Measured gap capture requested for '+selected()[0]);update();},true);
        button(zrecord,'Apply 3-point Z',function(){api.applyZ();heightMode.setSelectedItem('raw');note('Height model applied. Lift to clearance before dispensing.');update();},true);
        controls.add(new (J('javax.swing.JLabel'))('Repeat height measurements at R1, R15, R40. Gap must be physically measured; this is not auto-probing.'));
        controls.add(new (J('javax.swing.JLabel'))('Use NEEDLE Approach for the tip. Never use OpenPnP Move Nozzle to a placement: its rotation turns the paste gear.'));
        var run=row('4. Dispense',new (J('javax.swing.JLabel'))('Selected group:'));
        button(run,'Both pads',function(){var r=recipe();r.padMode='both';lastPadMode='both';api.dispense(selected(),r);},'dispense');
        button(run,'Pad 1 only',function(){var r=recipe();r.padMode='1';lastPadMode='1';api.dispense(selected(),r);},'dispense');
        button(run,'Pad 2 only',function(){var r=recipe();r.padMode='2';lastPadMode='2';api.dispense(selected(),r);},'dispense');
        var purgeDegrees=new (J('javax.swing.JSpinner'))(new (J('javax.swing.SpinnerNumberModel'))(new java.lang.Double(300),new java.lang.Double(1),new java.lang.Double(1000),new java.lang.Double(30)));
        var purgeSpeed=new (J('javax.swing.JSpinner'))(new (J('javax.swing.SpinnerNumberModel'))(new java.lang.Double(.5),new java.lang.Double(.01),new java.lang.Double(1),new java.lang.Double(.05)));
        var purgeRow=row('Purge at current position — degrees',purgeDegrees);purgeRow.add(new (J('javax.swing.JLabel'))('B speed'));purgeRow.add(purgeSpeed);
        var purgeConfirm=new (J('javax.swing.JCheckBox'))('Needle is hovering over scrap/waste, outside the PCB, not touching; I am watching.');controls.add(purgeConfirm);
        button(purgeRow,'PURGE at current position (no XYZ)',function(){if(!confirm.isSelected()||!purgeConfirm.isSelected())throw Error('Confirm supervision and needle hovering over scrap outside the PCB first');purgeDegrees.commitEdit();purgeSpeed.commitEdit();api.purge(Number(purgeDegrees.getValue()),Number(purgeSpeed.getValue()));note('Purge requested: forward B only, 30-degree chunks, no automatic retract or XYZ motion. STOP holds this position.');},false);
        var reliefDegrees=new (J('javax.swing.JSpinner'))(new (J('javax.swing.SpinnerNumberModel'))(new java.lang.Double(1),new java.lang.Double(1),new java.lang.Double(15),new java.lang.Double(1)));
        var reliefRow=row('Pressure relief at current position — degrees',reliefDegrees);reliefRow.add(new (J('javax.swing.JLabel'))('Uses purge B speed above; total pending relief capped at 15 degrees.'));
        button(reliefRow,'RELIEVE pressure (positive B, no XYZ)',function(){if(!confirm.isSelected()||!purgeConfirm.isSelected())throw Error('Confirm supervision and needle hovering over scrap outside the PCB first');reliefDegrees.commitEdit();purgeSpeed.commitEdit();api.relievePressure(Number(reliefDegrees.getValue()),Number(purgeSpeed.getValue()));note('Pressure relief requested: positive B only, no XYZ. Verified relief is tracked for the next dose; STOP holds position.');},false);
        var utility=row('',new (J('javax.swing.JLabel'))(''));
        var stopButton=button(utility,'STOP after current move',function(){api.stop();note('Stop requested after current move. Purge/pressure relief holds XYZ; pad dispensing lifts to clearance. Use the machine emergency stop for immediate stop.');},false);idleButtons.pop();
        button(utility,'Save recipe',function(){var folder=new F(root+'/automation/evidence/operator-recipes');folder.mkdirs();var file=new F(folder,'recipe-'+java.lang.System.currentTimeMillis()+'.json');var r={schema:1,recipe:recipe(),padMode:lastPadMode,references:selected(),profileId:profile.id};Files.write(file.toPath(),new java.lang.String(JSON.stringify(r,null,2)+'\n').getBytes(UTF));note('Recipe saved: '+file);},false);
        button(utility,'Load recipe',function(){if(busy)throw Error('Wait for the current run to finish');var chooser=new (J('javax.swing.JFileChooser'))(root+'/automation/evidence/operator-recipes');if(chooser.showOpenDialog(frame)===J('javax.swing.JFileChooser').APPROVE_OPTION){var saved=JSON.parse(read(String(chooser.getSelectedFile())));if(saved.schema!==1||saved.profileId!==profile.id||!saved.recipe||!Array.isArray(saved.references)||saved.references.some(function(r){return refs.indexOf(r)<0;}))throw Error('Recipe schema, profile or resistor selection does not match this session');heightMode.setSelectedItem(saved.recipe.heightMode==='gap'?'gap':'raw');Object.keys(fields).forEach(function(k){if(saved.recipe[k]!==undefined)fields[k].setValue(new java.lang.Double(saved.recipe[k]));});list.setSelectedIndices(Java.to(saved.references.map(function(r){return refs.indexOf(r);}),'int[]'));lastPadMode=saved.padMode||'both';note('Settings and selection loaded. Saved pad mode: '+lastPadMode+'. Choose the matching dispense button; no motion performed.');}},false);
        var scrollControls=new (J('javax.swing.JScrollPane'))(controls);scrollControls.getVerticalScrollBar().setUnitIncrement(24);panel.add(scrollControls,'Center');panel.add(new (J('javax.swing.JScrollPane'))(log),'South');
        frame.setContentPane(panel);frame.setDefaultCloseOperation(J('javax.swing.WindowConstants').DO_NOTHING_ON_CLOSE);
        frame.addWindowListener(new (Java.extend(J('java.awt.event.WindowAdapter')))({windowClosing:function(){api.stop();api.disarm();frame.dispose();}}));
        note('Check supervision, then Connect/check controller to enable camera and calibration controls. Opening does not move.');
        note('If fresh XY and a relative vacuum plane are imported: Approach Pad 1 while watching; record explicit needle barely touching, then Lift. Gap mode defaults to 0.20 mm above that zero.');
        note('Manual alternative: align R1/R15/R40, Apply XY, physically measure three needle gaps, Apply Z, then use raw height mode. Board replaced/reset invalidates all height references.');
        note('Profile: '+profile.id+'. Provisional height/offset; recipes are experiments, not volume calibration.');
        note('Run records: '+root+'/automation/evidence/operator-paste-runs');
        update();frame.pack();var screen=J('java.awt.Toolkit').getDefaultToolkit().getScreenSize();frame.setSize(Math.min(frame.getWidth(),screen.width-40),Math.min(frame.getHeight(),screen.height-80));frame.setLocation(Math.max(0,screen.width-frame.getWidth()-20),40);frame.setVisible(true);print('Paste console opened with explicit controller check and XY/Z calibration; motion not dispatched.');
    }}));
}());
