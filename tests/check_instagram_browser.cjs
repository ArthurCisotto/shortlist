const assert=require('node:assert/strict');
const {source,inspect,playwright}=require('../skills/shortlist/scripts/instagram-browser.cjs');
(async()=>{
  for(const target of ['..','accounts','direct','a/b','a?b']) assert.throws(()=>source('profile',target));
  assert.throws(()=>source('post','../anything'));
  assert.equal(source('profile','sample.bicycle.shop'),'https://www.instagram.com/sample.bicycle.shop/');
  const browser=await playwright().chromium.launch({headless:true,channel:'chrome'});
  try{
    const page=await browser.newPage();
    let mode='profile';
    await page.route('**/*',async route=>{
      if(mode==='limited')return route.fulfill({status:429,body:'limited'});
      if(mode==='login'&&!route.request().url().includes('/accounts/'))return route.fulfill({status:302,headers:{location:'https://www.instagram.com/accounts/login/'}});
      const head=mode==='post'?'<meta property="og:description" content="2 likes, 1 comments - sample.bicycle.shop on October 6, 2026: &quot;Hydraulic brake repairs&quot;. ">':'';
      const main=mode==='profile'?'<header>sample.bicycle.shop\nCRP and public bio</header><a href="/sample.bicycle.shop/p/ABC123/">Post</a><a href="/p/ABC123/c/comment/">Same post</a>':mode==='post'?'<article>Author caption then a visitor comment<time datetime="2026-10-06T12:00:00Z"></time></article>':'Log in to continue';
      return route.fulfill({status:200,contentType:'text/html',body:`<!doctype html><html><head><title>Synthetic Instagram</title>${head}</head><body><main>${main}</main></body></html>`});
    });
    const profile=await inspect(page,source('profile','sample.bicycle.shop'),'profile');
    assert.match(profile.profile_text,/CRP and public bio/);
    assert.deepEqual(profile.post_links,['https://www.instagram.com/p/ABC123/']);
    mode='post';const post=await inspect(page,source('post','ABC123'),'post');
    assert.equal(post.caption,'Hydraulic brake repairs');
    assert.equal(post.caption_author,'sample.bicycle.shop');
    assert.equal(post.caption_publication_label,'October 6, 2026');
    assert.equal(post.caption.includes('visitor comment'),false);
    mode='limited';await assert.rejects(()=>inspect(page,source('post','ABC123'),'post'),/RATE_LIMITED/);
    mode='login';await assert.rejects(()=>inspect(page,source('profile','sample.bicycle.shop'),'profile'),/LOGIN_REQUIRED/);
    mode='unavailable';await assert.rejects(()=>inspect(page,source('profile','sample.bicycle.shop'),'profile'),/ACCESS_UNAVAILABLE/);
    await assert.rejects(()=>inspect(page,source('post','ABC123'),'post'),/ACCESS_UNAVAILABLE/);
    console.log('PASS: public-page provenance, attributed captions without comment conflation, URL restrictions, source deduplication and honest login/rate/access failures.');
  }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
