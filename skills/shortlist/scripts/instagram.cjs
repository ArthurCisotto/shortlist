// Targeted read-only research using instagram-cli's installed API library.
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {createRequire} = require('node:module');
const {parseArgs} = require('node:util');
const HANDLE = /^(?!\.{1,2}$)[A-Za-z0-9_.]{1,30}$/;
const TOOL = path.join(os.homedir(), '.local/share/shortlist/instagram');
const messages = {
  AUTH_REQUIRED:'Complete local Instagram CLI login, then retry this read.',
  CHECKPOINT_REQUIRED:'Resolve the Instagram challenge manually; no automatic retries.',
  RATE_LIMITED:'Instagram limited access. Stop this batch and retry later.',
  NOT_FOUND:'The account could not be found; preserve this evidence gap.',
  CLIENT_MISSING:'Install @i7m/instagram-cli@2.0.1 in the documented tool directory.',
  CLIENT_UNPATCHED:'The client still uses the obsolete app version. Run setup-instagram.sh before logging in.',
  INVALID_RESPONSE:'Instagram returned an unexpected response; treat it as unverified.',
  REQUEST_FAILED:'Instagram read failed; no session details are included in this error.'
};
function problem(code) { return Object.assign(new Error(messages[code]), {code}); }
function classify(error) {
  if (Object.hasOwn(messages,error.code)) return error.code;
  if (/Checkpoint|Challenge/.test(error.name)) return 'CHECKPOINT_REQUIRED';
  if (/LoginRequired|CookieNotFound/.test(error.name) || error.response?.statusCode===401) return 'AUTH_REQUIRED';
  if (error.response?.statusCode===429 || /SentryBlock|Spam|Throttl/.test(error.name)) return 'RATE_LIMITED';
  if (error.response?.statusCode===404 || /UserNotFound/.test(error.name)) return 'NOT_FOUND';
  return 'REQUEST_FAILED';
}
function account(user) {
  if (!user || !HANDLE.test(user.username) || !user.pk) throw problem('INVALID_RESPONSE');
  return {id:String(user.pk),username:user.username,name:user.full_name||'',
    url:`https://www.instagram.com/${user.username}/`,private:!!user.is_private};
}
async function collect(ig,command,target,limit=6) {
  if (!['search','profile'].includes(command) || !Number.isInteger(limit) || limit<1 || limit>10) throw new Error('Invalid command or limit');
  if (typeof target!=='string' || !target.trim() || target.length>150 || (command==='profile'&&!HANDLE.test(target))) throw new Error('Invalid query or handle');
  const checked_at=new Date().toISOString().slice(0,10);
  if (command==='search') {
    const result=await ig.user.search(target);
    if (!Array.isArray(result.users)) throw problem('INVALID_RESPONSE');
    return {checked_at,accounts:result.users.slice(0,limit).map(account),coverage:'One account-search response; not an exhaustive caption or hashtag search.'};
  }
  const user=await ig.user.usernameinfo(target);
  const profile={...account(user),biography:user.biography||'',external_url:user.external_url||'',profile_photo_url:user.profile_pic_url||'',checked_at};
  if (profile.private) return {profile,posts:[],coverage:'Public profile fields only. Private posts were not requested.'};
  let items;
  try { items=await ig.feed.user(user.pk).items(); }
  catch(error) { const code=classify(error); return {profile,posts:[],coverage:'Bio retrieved; post inspection unavailable.',post_error:{code,message:messages[code]}}; }
  if (!Array.isArray(items)) throw problem('INVALID_RESPONSE');
  const posts=items.slice(0,limit).map(item=>{
    if (!/^[A-Za-z0-9_-]+$/.test(item.code||'') || !Number.isFinite(item.taken_at)) throw problem('INVALID_RESPONSE');
    return {url:`https://www.instagram.com/p/${item.code}/`,caption:item.caption?.text||'',
      published_at:new Date(item.taken_at*1000).toISOString(),checked_at};
  });
  return {profile,posts,coverage:'One page of recent profile posts; captions only. Images, reel speech, stories and highlights were not inspected.'};
}
function dependencies(tool=TOOL) {
  let result;
  try {
    const load=createRequire(path.join(tool,'package.json'));
    result={IgApiClient:load('instagram-private-api').IgApiClient,yaml:load('js-yaml')};
  } catch { throw problem('CLIENT_MISSING'); }
  if (new result.IgApiClient().state.appVersion==='222.0.0.13.114') throw problem('CLIENT_UNPATCHED');
  return result;
}
function sessionConfig(yaml,accountName) {
  const base=path.join(os.homedir(),'.instagram-cli');
  let config;
  try { config=yaml.load(fs.readFileSync(path.join(base,'config.ts.yaml'),'utf8')); }
  catch { throw problem('AUTH_REQUIRED'); }
  const username=accountName||config?.login?.currentUsername||config?.login?.defaultUsername;
  if (typeof username!=='string'||!HANDLE.test(username)) throw problem('AUTH_REQUIRED');
  const directory=config?.advanced?.usersDir||path.join(base,'users');
  if (typeof directory!=='string'||!path.isAbsolute(directory)) throw problem('AUTH_REQUIRED');
  let state;
  try { state=JSON.parse(fs.readFileSync(path.join(directory,username,'session.ts.json'),'utf8')); }
  catch { throw problem('AUTH_REQUIRED'); }
  if (!state || typeof state!=='object' || Array.isArray(state)) throw problem('AUTH_REQUIRED');
  return {username,state};
}
async function main() {
  const {values,positionals}=parseArgs({allowPositionals:true,options:{account:{type:'string'},limit:{type:'string',default:'6'},'tool-directory':{type:'string',default:TOOL}}});
  const [command,target]=positionals;
  if (!['doctor','status','search','profile'].includes(command)||positionals.length!==(['doctor','status'].includes(command)?1:2)) throw new Error('Usage: node instagram.cjs doctor | status | search QUERY | profile HANDLE [--limit 1..10] [--account HANDLE]');
  const {IgApiClient,yaml}=dependencies(values['tool-directory']);
  if (command==='doctor') return {installed:true,app_version:new IgApiClient().state.appVersion,authenticated_read_verified:false};
  const {username,state}=sessionConfig(yaml,values.account);
  if (command==='status') return {session_configured:true,authenticated_read_verified:false};
  const ig=new IgApiClient();
  ig.state.generateDevice(username);
  try { await ig.state.deserialize(state); } catch { throw problem('AUTH_REQUIRED'); }
  // ponytail: one response page per operation; add explicit pagination only when a real search needs it.
  return collect(ig,command,target,Number(values.limit));
}
if (require.main===module) {
  const timeout=setTimeout(()=>{console.log(JSON.stringify({ok:false,error:{code:'REQUEST_FAILED',message:'Instagram read timed out; stop this batch.'}}));process.exit(1);},45000);
  main().then(data=>{clearTimeout(timeout);console.log(JSON.stringify({ok:true,data}));},error=>{
    clearTimeout(timeout);const code=classify(error);
    console.log(JSON.stringify({ok:false,error:{code,message:messages[code]}}));process.exitCode=1;
  });
}
module.exports={collect,classify,sessionConfig,dependencies};
