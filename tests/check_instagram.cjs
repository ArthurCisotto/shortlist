const assert=require('node:assert/strict');
const fs=require('node:fs');
const os=require('node:os');
const path=require('node:path');
const {mock}=require('node:test');
const {collect,classify,dependencies,sessionConfig}=require('../skills/shortlist/scripts/instagram.cjs');
(async()=>{
  const calls=[];
  const user={pk:123,username:'sample.bicycle.shop',full_name:'Synthetic Example',biography:'Hydraulic brake repairs',is_private:false};
  const api={user:{search:async q=>{calls.push(['search',q]);return{users:[user,user]};},usernameinfo:async h=>{calls.push(['profile',h]);return user;}},feed:{user:id=>{calls.push(['posts',id]);return{items:async()=>[{code:'ABC_123',taken_at:1700000000,caption:{text:'Saturday appointments; price list available'}}]};}}};
  const search=await collect(api,'search','bicycle repair',1);
  assert.equal(search.accounts.length,1);
  assert.deepEqual(calls,[['search','bicycle repair']]);
  calls.length=0;
  const profile=await collect(api,'profile','sample.bicycle.shop');
  assert.deepEqual(calls,[['profile','sample.bicycle.shop'],['posts',123]]);
  assert.equal(profile.posts[0].url,'https://www.instagram.com/p/ABC_123/');
  assert.equal(profile.profile.biography,user.biography);
  assert.match(profile.coverage,/stories and highlights were not inspected/);
  user.is_private=true;calls.length=0;
  assert.equal((await collect(api,'profile',user.username)).posts.length,0);
  assert.deepEqual(calls,[['profile',user.username]]);
  user.is_private=false;
  api.feed.user=()=>({items:async()=>{throw Object.assign(new Error('secret-cookie'),{response:{statusCode:429}});}});
  const partial=await collect(api,'profile',user.username);
  assert.equal(partial.post_error.code,'RATE_LIMITED');
  assert.equal(JSON.stringify(partial).includes('secret-cookie'),false);
  assert.equal(classify({name:'IgLoginRequiredError'}),'AUTH_REQUIRED');
  assert.equal(classify({name:'IgCheckpointError'}),'CHECKPOINT_REQUIRED');
  assert.equal(classify({name:'UnexpectedError',message:'session-secret'}),'REQUEST_FAILED');
  await assert.rejects(()=>collect(api,'profile','../escape'));
  for(const value of ['.','..']){
    await assert.rejects(()=>collect(api,'profile',value));
    const paths=[];
    const read=mock.method(fs,'readFileSync',p=>{paths.push(p);return '{}';});
    try {
      assert.throws(()=>sessionConfig({load:()=>({advanced:{usersDir:'/tmp/example-users'}})},value));
      assert.equal(paths.length,1); // Config only; never read an escaped session path.
    } finally {read.mock.restore();}
  }
  await assert.rejects(()=>collect(api,'search','test',11));
  await assert.rejects(()=>collect(api,'inbox','test'));
  const {IgApiClient}=dependencies();
  const real=new IgApiClient();
  assert.equal(real.state.appVersion,'416.0.0.47.66');
  assert.equal(typeof real.user.usernameinfo,'function');
  assert.equal(typeof real.feed.user(123).items,'function');
  const stale=fs.mkdtempSync(path.join(os.tmpdir(),'swipe-stale-client-'));
  try {
    for(const name of ['instagram-private-api','js-yaml']) fs.mkdirSync(path.join(stale,'node_modules',name),{recursive:true});
    fs.writeFileSync(path.join(stale,'package.json'),'{}');
    fs.writeFileSync(path.join(stale,'node_modules/instagram-private-api/index.js'),"exports.IgApiClient=class {state={appVersion:'222.0.0.13.114'}};");
    fs.writeFileSync(path.join(stale,'node_modules/js-yaml/index.js'),'module.exports={};');
    assert.throws(()=>dependencies(stale),error=>error instanceof Error && 'code' in error && error.code==='CLIENT_UNPATCHED');
  } finally {fs.rmSync(stale,{recursive:true,force:true});}
  console.log('PASS: bounded account search, profile/caption provenance, private-post exclusion, redacted auth/rate errors, command limits and installed API compatibility. Live read requires login.');
})().catch(error=>{console.error(error);process.exitCode=1;});
