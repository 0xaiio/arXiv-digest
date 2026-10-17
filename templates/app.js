
var PD={papers:[],topics:[],weights:[],kw:{},pens:{},expand_ids:[]};
try{PD=JSON.parse(document.getElementById('pdata').textContent);}catch(e){}
var W=(PD.weights||[]).slice(), KW=PD.kw||{}, PENS=PD.pens||{};
var BYID={}; (PD.papers||[]).forEach(function(p){BYID[p.id]=p;});
var EXPSET={}; (PD.expand_ids||[]).forEach(function(i){EXPSET[i]=1;});
var DV={};
/* 页面可能被以 file:// 或别的静态服务打开，此时相对路径 /api/* 会打到错误的 origin。
   统一指向本地服务（同源时用相对路径，跨源/文件协议时用绝对地址 + CORS）。 */
var APIPORT=__APIPORT__;
var APIBASE=(location.protocol==='file:'||!location.port||location.port!==String(APIPORT))
  ?('http://127.0.0.1:'+APIPORT):'';
/* 站内链接（收藏 / 画像 / 存档 / 返回本期）同样要指向本地服务：
   页面被以 file:// 或别的静态服务打开时，href="/x" 会变成 file:///x 打不开。
   统一给所有根相对链接加上 APIBASE（同源时 APIBASE 为空串，等于没改）。 */
function fixLinks(){document.querySelectorAll('a[href^="/"]').forEach(function(a){
 var h=a.getAttribute('href');
 if(h.charAt(0)==='/'&&h.charAt(1)!=='/')a.setAttribute('href',APIBASE+h);});}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',fixLinks);
else fixLinks();
function toast(msg,kind){var w=document.getElementById('toast');if(!w){w=document.createElement('div');w.id='toast';document.body.appendChild(w);}
 var d=document.createElement('div');d.className='tst '+(kind||'');d.textContent=msg;w.appendChild(d);
 /* 报错信息通常较长，给它更长的停留时间，否则来不及看完就消失 */
 setTimeout(function(){d.style.transition='opacity .4s';d.style.opacity='0';setTimeout(function(){d.remove();},420);},kind==='err'?7000:2600);}
async function api(path,body){try{var r=await fetch(APIBASE+path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body||{})});return await r.json();}
 catch(e){return {ok:false,offline:true,msg:'本地服务未启动，请运行 start_digest.bat 后刷新'};}}
function applyProfile(p){if(!p)return;if(p.weights)W=p.weights;if(p.kw)KW=p.kw;if(p.pens)PENS=p.pens;}
function scoreOf(p){var s=p.base+(PENS[p.id]||0);
 for(var k=0;k<(p.tv||[]).length;k++){s+=p.tv[k][1]*W[p.tv[k][0]];}
 var t=p.toks||[];for(var j=0;j<t.length;j++){s+=(KW[t[j]]||0);}
 return s;}
function eachBtn(sid,fn){document.querySelectorAll('[data-sid="'+sid+'"]').forEach(fn);}
function setFav(sid,on){eachBtn(sid,function(b){if(b.dataset.act!=='fav')return;
 b.classList.toggle('on',on);var lb=b.querySelector('.lb');if(lb)lb.textContent=on?'已收藏':'收藏';
 var ic=b.querySelector('.ico');if(ic)ic.textContent=on?'★':'☆';});syncCount();}
function setDl(sid,on){eachBtn(sid,function(b){if(b.dataset.act!=='dl')return;
 b.classList.toggle('done',!!on);var lb=b.querySelector('.lb');if(lb)lb.textContent=on?'已下载':'下载';});}
function setDv(sid,on){if(on)DV[sid]=1;else delete DV[sid];
 eachBtn(sid,function(b){if(b.dataset.act!=='dv')return;b.classList.toggle('on',!!on);
  var lb=b.querySelector('.lb');if(lb)lb.textContent=on?'已 Downvote':'Downvote';});
 document.querySelectorAll('.rec-card[data-sid="'+sid+'"],li.item[data-sid="'+sid+'"],'
  +'.hl[data-sid="'+sid+'"],.fav-item[data-sid="'+sid+'"]')
  .forEach(function(e){e.classList.toggle('down',!!on);});
 /* 记住点击时卡片在列表里的位次：重排时按这个位次「钉」回原处，
    让 Downvote 在三个模块里一律只是「变灰 + 删除线」，不位移、不消失。 */
 document.querySelectorAll('#rec-list .rec-card[data-sid="'+sid+'"],#exp-list .rec-card[data-sid="'+sid+'"]')
  .forEach(function(c){
   if(!on){delete c.dataset.dvpos;return;}
   var sibs=[].slice.call(c.parentNode.children).filter(function(e){return e.classList.contains('rec-card');});
   var i=sibs.indexOf(c);if(i>=0)c.dataset.dvpos=i;});}
function syncCount(){var s={};document.querySelectorAll('.btn.fav.on').forEach(function(b){if(b.dataset.sid)s[b.dataset.sid]=1;});
 var c=document.getElementById('favcount');if(c)c.textContent=Object.keys(s).length;}
async function track(sid,action,extra){var body={id:sid,action:action};if(extra)for(var k in extra)body[k]=extra[k];
 var r=await api('/api/event',body);applyProfile(r.profile);
 /* 只刷新分数数字，绝不重排：展开 Abstract / 点 PDF 时列表不能动，否则像页面在刷新。 */
 if(action==='abstract'||action==='pdf')rescore();return r;}
/* ---- 并发与响应速度：乐观更新 + 合并重排 ----
   1) 点按钮立刻改界面（不等网络往返），请求在后台跑：一篇论文正在下载时，
      别的论文的 Downvote / 收藏 / 下载照常响应，不同操作真正并行。
   2) 重排（排序 + 重新编号 + 视口锚定）在 30ms 内合并成一次，连点不会
      反复重排整屏。 */
var _rsT=0,_rsNoAnchor=false;
function queueResort(noAnchor){if(noAnchor)_rsNoAnchor=true;
 if(_rsT)return;
 _rsT=setTimeout(function(){_rsT=0;var na=_rsNoAnchor;_rsNoAnchor=false;resort(na);},30);}
function toggleFav(sid){
 var b=document.querySelector('.btn.fav[data-act="fav"][data-sid="'+sid+'"]');
 var on=!(b&&b.classList.contains('on'));
 setFav(sid,on);                    /* 先改按钮，再发请求（失败回滚） */
 api(on?'/api/favorite':'/api/unfavorite',{id:sid}).then(function(r){
  if(!r.ok){setFav(sid,!on);queueResort();toast(r.msg||'操作失败','err');return;}
  applyProfile(r.profile);toast(on?'已收藏 ★ '+sid:'已取消收藏 '+sid,'ok');queueResort();});}
function doDl(sid,btn){if(btn)btn.disabled=true;var lb=btn?btn.querySelector('.lb'):null;var old=lb?lb.textContent:'';
 if(lb)lb.textContent='下载中…';
 api('/api/download',{id:sid}).then(function(r){
  if(btn){btn.disabled=false;if(lb)lb.textContent=old;}
  if(r.ok){setFav(sid,true);setDl(sid,r.path||true);applyProfile(r.profile);
   toast('已下载并收藏：'+((r.path||'').split(/[\\/]/).pop()||sid),'ok');queueResort();}
  else toast('下载失败：'+(r.msg||''),'err');});}
function toggleDv(sid){
 var on=!DV[sid];
 setDv(sid,on);                     /* 先变灰划线，再发请求（失败回滚） */
 api(on?'/api/downvote':'/api/undownvote',{id:sid}).then(function(r){
  if(!r.ok){setDv(sid,!on);queueResort();toast(r.msg||'操作失败','err');return;}
  applyProfile(r.profile);
  toast(on?'已 Downvote：'+sid+'（变灰划线，再点一次可撤销）':'已撤销 Downvote：'+sid,'ok');
  queueResort();});}
function toggleAbs(sid,btn){var box=document.getElementById('ab-'+sid);if(!box)return;
 var open=!box.classList.contains('open');box.classList.toggle('open',open);
 document.querySelectorAll('[data-act="abs"][data-sid="'+sid+'"]').forEach(function(b){
  b.classList.toggle('open',open);var ic=b.querySelector('.ico');if(ic)ic.textContent=open?'▾':'▸';});
 if(open)track(sid,'abstract');}
async function dlAll(){var ids=[];document.querySelectorAll('#rec-list .rec-card:not(.hidden):not(.down),#exp-list .rec-card:not(.hidden):not(.down)').forEach(function(e){ids.push(e.dataset.sid);});
 if(!ids.length){toast('没有可下载的推荐','err');return;}
 toast('开始批量下载 '+ids.length+' 篇…');
 var r=await api('/api/download_all',{ids:ids});
 if(!r.ok){toast(r.msg||'批量下载失败','err');return;}
 (r.results||[]).forEach(function(x){if(x.ok){setFav(x.id,true);setDl(x.id,x.path||true);}});
 toast('完成：'+(r.n_ok||0)+' / '+ids.length+' 篇已保存到 '+(STATE.dldir||''),'ok');}
/* ---- 视口稳定：重排时把当前可见的那篇论文「钉」在原位置，避免跳到页面顶部 ---- */
function pageY(){return window.pageYOffset||document.documentElement.scrollTop||document.body.scrollTop||0;}
function noSmooth(on){document.documentElement.classList.toggle('nosm',!!on);}
function saveAnchor(){
  var y=pageY(),best=null;
  document.querySelectorAll('#rec-list .rec-card,#exp-list .rec-card,.plist li.item,.hl').forEach(function(e){
    if(e.classList.contains('hidden'))return;
    var r=e.getBoundingClientRect();
    if(r.height&&r.bottom>0&&(!best||r.top<best.top))best={el:e,top:r.top,y:y};});
  return best||{el:null,top:0,y:y};}
function restoreAnchor(a){if(!a)return;
  noSmooth(true);
  var y=a.y;
  if(a.el&&a.el.isConnected&&!a.el.classList.contains('hidden')){
    var r=a.el.getBoundingClientRect();
    if(r.height)y=pageY()+(r.top-a.top);}
  y=Math.max(0,y);
  window.scrollTo(0,y);
  requestAnimationFrame(function(){window.scrollTo(0,y);noSmooth(false);});}
function rescore(){['rec-list','exp-list'].forEach(function(id){
 var box=document.getElementById(id);if(!box)return;
 box.querySelectorAll('.rec-card').forEach(function(c){
  var p=BYID[c.dataset.sid];var s=p?scoreOf(p):parseFloat(c.dataset.score||0);
  c.dataset.score=s.toFixed(2);var sc=c.querySelector('.score');if(sc)sc.textContent=s.toFixed(1);
  if(p){var tg=c.querySelector('.tag');if(tg&&p.primary)tg.textContent=p.primary;}});});}
function resort(noAnchor){var anchor=noAnchor?null:saveAnchor();
 rescore();
 ['rec-list','exp-list'].forEach(function(id){
 var box=document.getElementById(id);if(!box)return;
 var all=[].slice.call(box.querySelectorAll('.rec-card'));
 /* Downvote 的卡片一律不隐藏（与「分类详解」同一套逻辑：变灰 + 删除线），
    并钉在点击时记下的位次上，所以它既不消失也不跳到别处，再点一次即可撤销。
    data-limit 只约束「正常推荐」的条数，灰色卡片额外保留。 */
 var ups=all.filter(function(c){return !DV[c.dataset.sid];});
 var downs=all.filter(function(c){return DV[c.dataset.sid];});
 ups.sort(function(a,b){return parseFloat(b.dataset.score)-parseFloat(a.dataset.score);});
 var limit=parseInt(box.dataset.limit||'14',10),shown=0;
 ups.forEach(function(c){var hide=shown>=limit;c.classList.toggle('hidden',hide);if(!hide)shown++;});
 var cards=ups.slice();
 downs.forEach(function(c){
  c.classList.remove('hidden');
  var p=parseInt(c.dataset.dvpos||'',10);if(isNaN(p))p=cards.length;
  cards.splice(Math.max(0,Math.min(p,cards.length)),0,c);});
 /* 顺序没变就不动 DOM —— 逐个 appendChild 会造成整屏闪烁与跳动 */
 var cur=[].slice.call(box.children).filter(function(e){return e.classList.contains('rec-card');});
 var same=cur.length===cards.length;
 if(same)for(var i=0;i<cards.length;i++){if(cur[i]!==cards[i]){same=false;break;}}
 if(!same){var frag=document.createDocumentFragment();
  cards.forEach(function(c){frag.appendChild(c);});box.appendChild(frag);}
 var no=box.querySelectorAll('.rec-card:not(.hidden)');
 for(var j=0;j<no.length;j++){var e2=no[j].querySelector('.rec-no');if(e2)e2.textContent=('0'+(j+1)).slice(-2);}
 var em=box.querySelector('.empty');if(em)em.style.display=shown?'none':'';});
 restoreAnchor(anchor);updateRail();}
/* ---- 视口稳定结束 ---- */
/* ---- 侧边导航（分类横线）+ 回到顶部 ---- */
var RAIL=[];
function railInit(){RAIL=[];
 document.querySelectorAll('#rail .navi').forEach(function(n){
  var el=document.getElementById(n.dataset.target);
  if(el)RAIL.push({n:n,el:el});});
 updateRail();}
function updateRail(){if(!RAIL.length)return;
 var best=null;
 RAIL.forEach(function(t){var top=t.el.getBoundingClientRect().top;
  if(top<=150&&(!best||top>best.top))best={item:t,top:top};});
 var act=best?best.item:RAIL[0];
 RAIL.forEach(function(t){t.n.classList.toggle('on',t===act);});}
/* 用 setTimeout 节流而不是 requestAnimationFrame：后台标签页/无头环境里 rAF 会停摆，
   导致高亮更新滞后甚至不更新。 */
var _st=0;
function onScroll(){if(_st)return;_st=setTimeout(function(){_st=0;
 updateRail();
 var b=document.getElementById('totop');if(b)b.classList.toggle('show',pageY()>420);},90);}
function openFolder(){api('/api/open_folder',{}).then(function(r){if(!r.ok)toast(r.msg||'打开失败','err');});}
async function openPaper(sid){var r=await api('/api/open',{id:sid});if(!r.ok)toast(r.msg||'尚未下载该论文','err');}
function applyFilter(mode){document.querySelectorAll('.tb[data-mode]').forEach(function(b){b.classList.toggle('on',b.dataset.mode===mode);});
 var q=(document.getElementById('q').value||'').toLowerCase();
 document.querySelectorAll('li.item').forEach(function(li){
   var sid=li.dataset.sid, ok=true;
   if(mode==='fav'&&!li.querySelector('.btn.fav.on'))ok=false;
   if(mode==='dl'&&!li.querySelector('.btn.dl.done'))ok=false;
   if(mode==='dv'&&!DV[sid])ok=false;
   if(ok&&q)ok=(li.textContent||'').toLowerCase().indexOf(q)>=0;
   li.classList.toggle('hidden',!ok);});
 document.querySelectorAll('.cat').forEach(function(s){
   var vis=s.querySelectorAll('li.item:not(.hidden)').length;
   s.style.display=(q||mode!=='all')?(vis?'':'none'):'';});}
var STATE={dldir:''};
document.addEventListener('click',function(ev){
 var b=ev.target.closest('button[data-act]');
 if(b){ev.preventDefault();var sid=b.dataset.sid,a=b.dataset.act;
  if(a==='fav')toggleFav(sid);else if(a==='dl')doDl(sid,b);
  else if(a==='abs')toggleAbs(sid,b);else if(a==='dv')toggleDv(sid,b);return;}
 var p=ev.target.closest('a.pdf[data-sid]');if(p){track(p.dataset.sid,'pdf');return;}
 var o=ev.target.closest('button[data-open]');if(o){openPaper(o.dataset.open);}});
document.addEventListener('DOMContentLoaded',function(){
 var q=document.getElementById('q');
 if(q)q.addEventListener('input',function(){var m=(document.querySelector('.tb[data-mode].on')||{dataset:{mode:'all'}}).dataset.mode;applyFilter(m);});
 document.querySelectorAll('.tb[data-mode]').forEach(function(b){b.addEventListener('click',function(){applyFilter(b.dataset.mode);});});
 var da=document.getElementById('dlall');if(da)da.addEventListener('click',dlAll);
 var of=document.getElementById('openfolder');if(of)of.addEventListener('click',openFolder);
 var fl=document.getElementById('favlink');if(fl)fl.href=APIBASE+'/favorites';
 var pf=document.getElementById('proflink');if(pf)pf.href=APIBASE+'/profile';
 railInit();
 var tt=document.getElementById('totop');
 if(tt)tt.addEventListener('click',function(){window.scrollTo({top:0,behavior:'smooth'});});
 window.addEventListener('scroll',onScroll,{passive:true});
 window.addEventListener('resize',railInit);
 onScroll();
 fetch(APIBASE+'/api/state').then(function(r){return r.json();}).then(function(s){
   STATE.dldir=s.download_dir||'';
   document.querySelectorAll('.dldir,.dldir-m').forEach(function(e){
     if(STATE.dldir)e.textContent=STATE.dldir;});
   (s.favorites||[]).forEach(function(id){setFav(id,true);});
   Object.keys(s.downloads||{}).forEach(function(id){setDl(id,s.downloads[id]);});
   (s.downvotes||[]).forEach(function(id){setDv(id,true);});
   applyProfile(s.profile);syncCount();resort(true);
  }).catch(function(){toast('本地服务未运行：收藏/下载/Downvote 不可用，请运行 start_digest.bat','err');});});
