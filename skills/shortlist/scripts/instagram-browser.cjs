// Public Instagram evidence through clean Chrome, without mobile-API login.
const os=require('node:os');
const path=require('node:path');
const {parseArgs}=require('node:util');
const HANDLE=/^(?!\.{1,2}$)[A-Za-z0-9_.]{1,30}$/;
const RESERVED=new Set(['accounts','direct','explore','stories','reels','p','reel','about','legal','privacy','web']);
function source(command,target){
  if(command==='profile'&&HANDLE.test(target)&&!RESERVED.has(target.toLowerCase())) return `https://www.instagram.com/${target}/`;
  if(command==='post'&&/^[A-Za-z0-9_-]{1,100}$/.test(target)) return `https://www.instagram.com/p/${target}/`;
  throw new Error('INVALID_INPUT');
}
function playwright(){
  const options=[process.env.SHORTLIST_PLAYWRIGHT,path.join(os.homedir(),'.local/share/shortlist/instagram-browser/node_modules/playwright'),path.join(os.homedir(),'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright')];
  for(const location of options.filter(Boolean)) {try{return require(location);}catch{}}
  throw new Error('BROWSER_TOOL_MISSING');
}
async function inspect(page,url,command){
  const response=await page.goto(url,{waitUntil:'domcontentloaded',timeout:30000});
  if(response?.status()===429) throw new Error('RATE_LIMITED');
  if(response?.status()===404) throw new Error('NOT_FOUND');
  if(response&&response.status()>=400) throw new Error('ACCESS_UNAVAILABLE');
  if(new URL(page.url()).pathname.startsWith('/accounts/')) throw new Error('LOGIN_REQUIRED');
  await page.locator('main').waitFor({timeout:15000});
  await page.waitForFunction(()=>!!document.querySelector('main')?.textContent?.trim(),null,{timeout:15000});
  const final=new URL(page.url());
  const expected=new URL(url);
  if(final.origin!==expected.origin||final.pathname.toLowerCase()!==expected.pathname.toLowerCase()) throw new Error('UNVERIFIED_REDIRECT');
  const result=await page.evaluate(()=>{
    const main=document.querySelector('main');
    const header=main.querySelector('header');
    const postLinks=[...new Set([...main.querySelectorAll('a[href]')].map(a=>a.getAttribute('href')).filter(h=>/\/(?:p|reel)\/[A-Za-z0-9_-]+\//.test(h)))].slice(0,10);
    return {profile_text:header?.innerText||'',visible_text:main.innerText.slice(0,12000),description:document.querySelector('meta[property="og:description"]')?.getAttribute('content')||'',
      post_paths:postLinks,title:document.title,
      timestamps:[...main.querySelectorAll('time[datetime]')].slice(0,20).map(t=>({datetime:t.getAttribute('datetime'),link:t.closest('a')?.getAttribute('href')||null}))};
  });
  if(!result.visible_text.trim()) throw new Error('ACCESS_UNAVAILABLE');
  if(command==='profile'&&!result.profile_text.split(/\s+/).some(t=>t.toLowerCase()===expected.pathname.split('/')[1].toLowerCase())) throw new Error('ACCESS_UNAVAILABLE');
  const caption=command==='post'?result.description.match(/^.*? - ([A-Za-z0-9_.]{1,30}) on ([^:]+): "([\s\S]*)"\.\s*$/):null;
  if(command==='post'&&!caption) throw new Error('ACCESS_UNAVAILABLE');
  const post_links=[...new Set(result.post_paths.map(p=>p.match(/\/(?:p|reel)\/([A-Za-z0-9_-]+)\//)?.[1]).filter(Boolean).map(code=>source('post',code)))];
  return {url:final.href,title:result.title,checked_at:new Date().toISOString().slice(0,10),
    profile_text:command==='profile'?result.profile_text:'',caption:caption?.[3]||'',caption_author:caption?.[1]||'',caption_publication_label:caption?.[2]||'',caption_source:caption?'page_metadata':null,
    visible_text:result.visible_text,post_links,timestamps:result.timestamps,
    coverage:'One public page rendered in clean Chrome. Caption metadata may be truncated. Visible text may include interface labels and comments; only attributed author text supports a provider claim. Timestamps can include comments. Images, video speech, stories and highlights were not inspected.'};
}
const ERRORS={INVALID_INPUT:'Use profile HANDLE or post SHORTCODE only.',BROWSER_TOOL_MISSING:'Install Playwright using the documented browser setup.',LOGIN_REQUIRED:'This page requires browser sign-in; public inspection is unavailable.',RATE_LIMITED:'Instagram limited access. Stop this batch.',NOT_FOUND:'Public Instagram page was not found.',ACCESS_UNAVAILABLE:'Public page could not be inspected.',UNVERIFIED_REDIRECT:'Instagram redirected away from the requested page; identity is unverified.',READ_FAILED:'Browser read failed; no private browser/session details are included.'};
async function main(){
  const {values,positionals}=parseArgs({allowPositionals:true,options:{visible:{type:'boolean',default:false}}});
  if(positionals.length!==2) throw new Error('INVALID_INPUT');
  const [command,target]=positionals;
  const url=source(command,target);
  const browser=await playwright().chromium.launch({headless:!values.visible,channel:'chrome'});
  try{return await inspect(await browser.newPage(),url,command);}finally{await browser.close();}
}
if(require.main===module){
  main().then(data=>console.log(JSON.stringify({ok:true,data})),error=>{
    const code=Object.hasOwn(ERRORS,error.message)?error.message:'READ_FAILED';
    console.log(JSON.stringify({ok:false,error:{code,message:ERRORS[code]}}));process.exitCode=1;
  });
}
module.exports={source,inspect,playwright};
