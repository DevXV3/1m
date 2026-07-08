const { chromium } = require('playwright'); const fs=require('fs');
const BASE='http://127.0.0.1:3000';
let pw=(fs.readFileSync('C:/Users/AiMiniX/open-webui/setup_rag_channels.py','utf8').match(/ADMIN_PASSWORD\s*=\s*"([^"]+)"/)||[])[1];
(async()=>{const b=await chromium.launch({headless:true});const p=await b.newPage({viewport:{width:1400,height:950}});
 await p.addInitScript(()=>{try{localStorage.setItem('theme','dark')}catch{}});
 await p.goto(BASE+'/auth',{waitUntil:'networkidle'}); await p.fill('input[type="email"]','claude@pingzy.local'); await p.fill('input[type="password"]',pw); await p.click('button[type="submit"]'); await p.waitForTimeout(4000);
 for(let i=0;i<4;i++){await p.keyboard.press('Escape');await p.waitForTimeout(200);}
 await p.goto(BASE+'/?models=spike_marker',{waitUntil:'networkidle'}); await p.waitForTimeout(2000);
 for(let i=0;i<3;i++){await p.keyboard.press('Escape');await p.waitForTimeout(200);}
 let inp=p.locator('#chat-input,div[contenteditable="true"],textarea').last(); await inp.click(); await p.keyboard.type('เริ่ม'); await p.keyboard.press('Enter');
 await p.waitForTimeout(10000);
 let fr=null; for(const f of p.frames()){try{if(await f.locator('#pz-ask').count()){fr=f;break;}}catch{}}
 if(!fr){console.log('no frame');await b.close();return;}
 const probe=await fr.evaluate(()=>{
   const cs=el=>getComputedStyle(el);
   const q=document.querySelector('.qtext'), card=document.querySelector('.opt');
   return { htmlClass:document.documentElement.className,
     parentDark:(()=>{try{return window.parent.document.documentElement.classList.contains('dark')}catch(e){return 'ERR:'+e.message}})(),
     qColor:q?cs(q).color:null, cardBg:card?cs(card).backgroundColor:null, rootFg:cs(document.documentElement).getPropertyValue('--fg') };
 });
 console.log(JSON.stringify(probe,null,1));
 await b.close();})();
