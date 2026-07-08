const { chromium } = require('playwright'); const fs=require('fs');
const BASE='http://127.0.0.1:3000';
let pw=(fs.readFileSync('C:/Users/AiMiniX/open-webui/setup_rag_channels.py','utf8').match(/ADMIN_PASSWORD\s*=\s*"([^"]+)"/)||[])[1];
(async()=>{const b=await chromium.launch({headless:true});const p=await b.newPage({viewport:{width:1400,height:950}});
 await p.goto(BASE+'/auth',{waitUntil:'networkidle'}); await p.fill('input[type="email"]','claude@pingzy.local'); await p.fill('input[type="password"]',pw); await p.click('button[type="submit"]'); await p.waitForTimeout(4000);
 for(let i=0;i<4;i++){await p.keyboard.press('Escape');await p.waitForTimeout(250);}
 await p.goto(BASE+'/?models=pztest-ask',{waitUntil:'networkidle'}); await p.waitForTimeout(2500);
 for(let i=0;i<3;i++){await p.keyboard.press('Escape');await p.waitForTimeout(250);}
 let inp=p.locator('#chat-input,div[contenteditable="true"],textarea').last(); await inp.click(); await p.keyboard.type('เริ่ม'); await p.keyboard.press('Enter');
 await p.waitForTimeout(12000);
 let fr=null; for(const f of p.frames()){try{if(await f.locator('#pz-ask').count()){fr=f;break;}}catch{}}
 if(fr){ const spec=await fr.evaluate(()=>JSON.stringify(window.PZ_ASK_SPEC)); console.log('PZ_ASK_SPEC=',spec); }
 else console.log('no frame');
 // also dump raw streamed message text from DOM (assistant bubble)
 const txt=await p.evaluate(()=>document.body.innerText); console.log('BODY_HAS_MARKER=', txt.includes('[[PINGZY_ASK]]'));
 await b.close();})();
