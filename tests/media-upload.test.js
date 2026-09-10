const { test } = require('node:test');
const assert = require('node:assert/strict');
const { uploadDashboardMedia } = require('../media-upload.js');
function start() {
  const xhr = { upload: {}, headers: {}, open(...args) { this.request = args; }, setRequestHeader(k,v) { this.headers[k]=v; }, send(body) { this.body=body; } };
  const progress = [];
  const result = uploadDashboardMedia({ url: '/api/ai/import-media', file: new Blob(['video']), token: 'test', onProgress: p=>progress.push(p), xhrFactory: ()=>xhr });
  return { xhr, progress, result };
}
test('multipart transfer reports progress and resolves only after server confirmation', async()=> {
  const {xhr,progress,result}=start();
  assert.deepEqual(xhr.request,['POST','/api/ai/import-media']);
  assert.equal(xhr.headers.Authorization,'Bearer test');
  assert.equal(xhr.headers['Content-Type'],undefined);
  assert.ok(xhr.body.get('file'));
  xhr.upload.onprogress({lengthComputable:true,loaded:22,total:44});
  xhr.upload.onprogress({lengthComputable:true,loaded:44,total:44});
  assert.deepEqual(progress,[50,100]);
  xhr.status=200;xhr.responseText=JSON.stringify({filename:'video.mp4'});xhr.onload();
  assert.equal((await result).filename,'video.mp4');
});
for (const [status,body,message] of [[413,'<html>Too large</html>',/60 MiB/],[401,'{}',/Sign in again/],[507,'{"error":"Storage full"}',/Storage full/],[502,'<html>Bad Gateway</html>',/HTTP 502/],[200,'{}',/Upload failed/]]) {
  test(`HTTP ${status} gives actionable error`,async()=> {
    const {xhr,result}=start();xhr.status=status;xhr.responseText=body;xhr.onload();await assert.rejects(result,message);
  });
}
for (const [event,message] of [['onerror',/connection/],['ontimeout',/timed out/],['onabort',/cancelled/]]) {
  test(`${event} does not report success`,async()=> {const {xhr,result}=start();xhr[event]();await assert.rejects(result,message);});
}

for (const maxMiB of [20,60]) {
  test(`oversize ${maxMiB} MiB file is rejected before opening a request`,async()=> {
    let opened=false;
    const result=uploadDashboardMedia({url:'/upload',file:{size:maxMiB*1024*1024+1},maxMiB,xhrFactory:()=>{opened=true;throw new Error('unexpected transfer');}});
    await assert.rejects(result,new RegExp(`max ${maxMiB} MiB`));
    assert.equal(opened,false);
  });
}
