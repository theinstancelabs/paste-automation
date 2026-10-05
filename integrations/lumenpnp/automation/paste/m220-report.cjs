/* Strict read-only report parser for bare Marlin M220. */
(function(root){
 'use strict';
 function fail(message){throw Error(message);}
 function parse(lines){
  if(!Array.isArray(lines)||lines.length!==2)fail('Bare M220 must return exactly one FR report and one terminal ok');
  var report=String(lines[0]).trim(),ack=String(lines[1]).trim();
  var match=/^(?:echo:\s*)?FR:\s*(\d{1,3})%$/.exec(report);
  if(!match||!/^ok(?:\s|$)/i.test(ack))fail('Bare M220 response must be FR:<0..999>% followed by terminal ok');
  return Number(match[1]);
 }
 var api={parse:parse};root.PasteM220Report=api;if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(this);
