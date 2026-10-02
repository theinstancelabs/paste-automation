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
        var fields = {}, buttons = [], armed = false, busy = false, lastPadMode = 'both';
        var log = new (J('javax.swing.JTextArea'))(9,70); log.setEditable(false); log.setLineWrap(true); log.setWrapStyleWord(true);
        function note(s){log.append(String(s)+'\n');log.setCaretPosition(log.getDocument().getLength());}
        function row(label, component){var p=new (J('javax.swing.JPanel'))(new (J('java.awt.FlowLayout'))(J('java.awt.FlowLayout').LEFT));p.add(new (J('javax.swing.JLabel'))(label));p.add(component);controls.add(p);return p;}
        function number(key,label,value,min,max,step){var spinner=new (J('javax.swing.JSpinner'))(new (J('javax.swing.SpinnerNumberModel'))(new java.lang.Double(value),new java.lang.Double(min),new java.lang.Double(max),new java.lang.Double(step)));fields[key]=spinner;row(label,spinner);}
        number('doseDegrees','Dose per pad (motor degrees)',6,0.25,30,0.25);
        number('retractPercent','Retraction between resistors (%)',15,0,50,5);
        number('dwellMs','Wait after each dose (ms)',2000,0,5000,100);
        number('retractDwellMs','Wait after retraction (ms)',500,0,2000,100);
        number('bSpeedFraction','Extrusion motor speed (fraction)',0.05,0.01,1,0.01);
        number('workZ','Needle work Z — larger = lower (mm)',profile.workZ,55,58.2,0.05);
        controls.add(new (J('javax.swing.JLabel'))('XY/Z travel stays at 100%. No retraction between the two pads.'));
        controls.add(new (J('javax.swing.JLabel'))('Work Z is checked against the stored surface clearance for each pad.'));
        var confirm=new (J('javax.swing.JCheckBox'))('I am watching; board position is unchanged, selected pads usable, motion area clear.');
        controls.add(confirm);
        function selected(){var a=[],values=list.getSelectedValuesList();for(var i=0;i<values.size();i++)a.push(String(values.get(i)));if(!a.length)throw Error('Select at least one resistor');return a;}
        function recipe(){if(busy)throw Error('Wait for the current run to finish');var r={};Object.keys(fields).forEach(function(k){fields[k].commitEdit();r[k]=Number(fields[k].getValue());});return r;}
        function update(){buttons.forEach(function(b){b.setEnabled(armed&&!busy);});Object.keys(fields).forEach(function(k){fields[k].setEnabled(!busy);});list.setEnabled(!busy);confirm.setEnabled(!busy);}
        var api=PasteOperator.create(profile,function(event){Swing.invokeLater(new (J('java.lang.Runnable'))({run:function(){if(event.busy!==undefined)busy=!!event.busy;if(event.armed!==undefined)armed=!!event.armed;if(event.error){armed=false;note('STOPPED: '+event.error);}if(event.message)note(event.message);if(event.record)note('Saved: '+event.record);update();}}));});
        function call(fn){try{fn();}catch(e){note('Not run: '+e);}}
        confirm.addActionListener(new (J('java.awt.event.ActionListener'))({actionPerformed:function(){call(function(){if(confirm.isSelected()){api.arm();note('Checking controller and arming operator controls…');}else{api.disarm();armed=false;}update();});}}));
        function button(parent,label,fn,motion){var b=new (J('javax.swing.JButton'))(label);b.addActionListener(new (J('java.awt.event.ActionListener'))({actionPerformed:function(){call(fn);}}));parent.add(b);if(motion)buttons.push(b);return b;}
        var nav=row('Camera',new (J('javax.swing.JLabel'))('Selected resistor:'));
        ['1','2','center'].forEach(function(p){button(nav,p==='center'?'Center':'Pad '+p,function(){api.jump(selected()[0],p);},true);});
        var run=row('Dispense',new (J('javax.swing.JLabel'))('Selected group:'));
        button(run,'Both pads',function(){var r=recipe();r.padMode='both';lastPadMode='both';api.dispense(selected(),r);},true);
        button(run,'Pad 1 only',function(){var r=recipe();r.padMode='1';lastPadMode='1';api.dispense(selected(),r);},true);
        button(run,'Pad 2 only',function(){var r=recipe();r.padMode='2';lastPadMode='2';api.dispense(selected(),r);},true);
        var utility=row('',new (J('javax.swing.JLabel'))(''));
        button(utility,'STOP after current move',function(){api.stop();note('Stop requested; let the active move finish. Use the machine emergency stop for an immediate stop.');},false);
        button(utility,'Save recipe',function(){var folder=new F(root+'/automation/evidence/operator-recipes');folder.mkdirs();var file=new F(folder,'recipe-'+java.lang.System.currentTimeMillis()+'.json');var r={schema:1,recipe:recipe(),padMode:lastPadMode,references:selected(),profileId:profile.id};Files.write(file.toPath(),new java.lang.String(JSON.stringify(r,null,2)+'\n').getBytes(UTF));note('Recipe saved: '+file);},false);
        button(utility,'Load recipe',function(){if(busy)throw Error('Wait for the current run to finish');var chooser=new (J('javax.swing.JFileChooser'))(root+'/automation/evidence/operator-recipes');if(chooser.showOpenDialog(frame)===J('javax.swing.JFileChooser').APPROVE_OPTION){var saved=JSON.parse(read(String(chooser.getSelectedFile())));if(saved.schema!==1||saved.profileId!==profile.id||!saved.recipe||!Array.isArray(saved.references)||saved.references.some(function(r){return refs.indexOf(r)<0;}))throw Error('Recipe schema, profile or resistor selection does not match this session');Object.keys(fields).forEach(function(k){if(saved.recipe[k]!==undefined)fields[k].setValue(new java.lang.Double(saved.recipe[k]));});list.setSelectedIndices(Java.to(saved.references.map(function(r){return refs.indexOf(r);}),'int[]'));lastPadMode=saved.padMode||'both';note('Settings and selection loaded. Saved pad mode: '+lastPadMode+'. Choose the matching dispense button; no motion performed.');}},false);
        panel.add(controls,'Center');panel.add(new (J('javax.swing.JScrollPane'))(log),'South');
        frame.setContentPane(panel);frame.setDefaultCloseOperation(J('javax.swing.WindowConstants').DO_NOTHING_ON_CLOSE);
        frame.addWindowListener(new (Java.extend(J('java.awt.event.WindowAdapter')))({windowClosing:function(){api.stop();api.disarm();frame.dispose();}}));
        note('Select resistor(s), verify the board, then check the operator box. Camera buttons do not dispense.');
        note('Profile: '+profile.id+'. Provisional height/offset; recipes are experiments, not volume calibration.');
        note('Run records: '+root+'/automation/evidence/operator-paste-runs');
        update();frame.pack();var screen=J('java.awt.Toolkit').getDefaultToolkit().getScreenSize();frame.setLocation(Math.max(0,screen.width-frame.getWidth()-20),40);frame.setVisible(true);
    }}));
}());
