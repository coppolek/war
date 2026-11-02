#!/usr/bin/env python3
"""Genera public/index.html (versione standalone/PWA) dal sorgente del gioco.
Uso: python3 build.py [percorso/sorgente.html]"""
import sys,os
src=sys.argv[1] if len(sys.argv)>1 else os.path.join(os.path.dirname(__file__),'..','dune-gunship.html')
s=open(src,encoding='utf-8').read()
def rep(a,b):
    global s
    assert s.count(a)==1,(a[:60],s.count(a)); s=s.replace(a,b)

ADAPTER=r"""
/* ---------- rete standalone: adattatore WebSocket con la stessa interfaccia di "room" ---------- */
function wsRoom(){
  return new Promise(resolve=>{
    const url=window.RG_WS||((location.protocol==='https:'?'wss://':'ws://')+location.host+'/ws');
    let ws;try{ws=new WebSocket(url)}catch(e){return resolve(null)}
    const H={},peers=new Map();let peerCb=null,closeCb=null,me=null,done=false;
    const emitPeers=j=>{if(!peerCb)return;peerCb({peers:[...peers.values()].sort((a,b)=>a.peer<b.peer?-1:1),joined:j||[]})};
    const raw=o=>{if(ws.readyState===1)ws.send(JSON.stringify(o))};
    const room={
      onPeers(cb,cl){peerCb=cb;closeCb=cl;emitPeers([])},
      on(t,f){H[t]=f},
      emit(t,d){raw({k:'e',t,d});return Promise.resolve()},
      presence(o){const m=peers.get(me);if(!m)return Promise.resolve();Object.assign(m.presence,o);if(ws.bufferedAmount<32768)raw({k:'p',d:m.presence});return Promise.resolve()}
    };
    const to=setTimeout(()=>{if(!done){done=true;try{ws.close()}catch(e){}resolve(null)}},7000);
    ws.onopen=()=>{raw({k:'join',room:new URLSearchParams(location.search).get('r')||''})};
    ws.onmessage=ev=>{let m;try{m=JSON.parse(ev.data)}catch(e){return}
      if(m.k==='welcome'){me=m.id;net.code=m.room;peers.clear();
        for(const p of m.peers)peers.set(p.peer,{peer:p.peer,kind:'viewer',isMe:p.peer===me,presence:p.p||{},updatedAt:Date.now()});
        if(!done){done=true;clearTimeout(to);resolve(room)}emitPeers([])}
      else if(m.k==='join'){const o={peer:m.peer,kind:'viewer',isMe:false,presence:{},updatedAt:Date.now()};peers.set(m.peer,o);emitPeers([o])}
      else if(m.k==='left'){peers.delete(m.id);emitPeers([])}
      else if(m.k==='p'){const o=peers.get(m.id);if(o){o.presence=m.d;o.updatedAt=Date.now()}}
      else if(m.k==='e'){const f=H[m.t];if(f)f({isMe:false,data:m.d,from:m.from})}
      else if(m.k==='full'){net.err='Stanza piena (massimo 6 piloti). Riprova o usa un altro codice stanza.';if(!done){done=true;clearTimeout(to);resolve(null)}}
    };
    ws.onclose=()=>{if(!done){done=true;clearTimeout(to);resolve(null)}else if(closeCb)closeCb()};
    ws.onerror=()=>{};
  });
}
"""
rep("async function netConnect(){",ADAPTER+"async function netConnect(){")
rep("try{const c=(window.claude&&window.claude.use)?await window.claude.use('room'):null;net.room=c||false}catch(e){net.room=false}",
    "try{let c=(window.claude&&window.claude.use)?await window.claude.use('room'):null;if(!c&&window.RG_STANDALONE)c=await wsRoom();net.room=c||false}catch(e){net.room=false}")
rep("if(!net.room){net.err='Multiplayer non disponibile qui. Apri il link da un account invitato con accesso da Collaboratore (non da link pubblico).';return false}",
    "if(!net.room){if(!net.err)net.err=window.RG_STANDALONE?'Impossibile collegarsi al server di gioco. Controlla la connessione e riprova.':'Multiplayer non disponibile qui. Apri il link da un account invitato con accesso da Collaboratore (non da link pubblico).';return false}")
rep("net.err='';\n  if(net.room===null){","if(net.room===false)net.room=null;\n  net.err='';\n  if(net.room===null){")
rep("const net={on:false,","const net={code:'',on:false,")
# lobby: testo e pulsante invito
rep("    wrap('Condividi il link con gli amici (accesso da Collaboratore) e apritelo insieme: si gioca in cooperazione sulla stessa missione. Punti e obiettivi sono condivisi, ogni pilota ha le sue vite.',cx,y+16,Math.min(520,w-48),20,13,'rgba(243,230,200,.7)');\n    uiBtn('INIZIA LA MISSIONE','INVIO',()=>advance(),cx-150,y+84,isTouch);\n    uiBtn('INDIETRO','ESC',()=>leaveLobby(),cx-150,y+132,isTouch);",
"""    const inv=window.RG_STANDALONE&&net.code;
    wrap(inv?('Stanza '+net.code+'. Per giocare con gli amici mandate loro il link d\\'invito: entrerete tutti nella stessa stanza (fino a 6 piloti, da PC, telefono o tablet). Punti e obiettivi sono condivisi, ogni pilota ha le sue vite.'):'Condividi il link con gli amici (accesso da Collaboratore) e apritelo insieme: si gioca in cooperazione sulla stessa missione. Punti e obiettivi sono condivisi, ogni pilota ha le sue vite.',cx,y+16,Math.min(520,w-48),20,13,'rgba(243,230,200,.7)');
    uiBtn('INIZIA LA MISSIONE','INVIO',()=>advance(),cx-150,y+84,isTouch);
    if(inv){uiBtn(lobbyCopied>0?'LINK COPIATO!':'COPIA LINK INVITO','LINK',()=>{const u=location.origin+location.pathname+'?r='+net.code+(curMap!=='rimini'?'&m='+curMap:'');try{navigator.clipboard.writeText(u);lobbyCopied=2}catch(e){prompt('Link invito',u)}},cx-150,y+132,isTouch)}
    uiBtn('INDIETRO','ESC',()=>leaveLobby(),cx-150,y+(inv?180:132),isTouch);""")
rep("const btns=[];","const btns=[];let lobbyCopied=0;")
rep("{time2+=dt;tx=","{time2+=dt;lobbyCopied-=dt;tx=")

head="""<!doctype html>
<html lang="it">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no,viewport-fit=cover">
<meta name="theme-color" content="#17130e">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="Riviera Gunship">
<meta name="description" content="Riviera Gunship: elicottero d'assalto isometrico a Rimini, co-op fino a 6 piloti su ogni dispositivo.">
<link rel="manifest" href="manifest.webmanifest">
<link rel="icon" type="image/png" href="icons/icon-192.png">
<link rel="apple-touch-icon" href="icons/apple-touch-icon.png">
<script>window.RG_STANDALONE=1;</script>
"""
tail="""
<script>
/* PWA: service worker + schermo intero/landscape al primo tocco su dispositivi touch */
if('serviceWorker' in navigator)addEventListener('load',()=>navigator.serviceWorker.register('sw.js').catch(()=>{}));
addEventListener('pointerdown',function f(e){
  if(e.pointerType!=='touch')return;removeEventListener('pointerdown',f);
  try{const d=document.documentElement;if(!document.fullscreenElement&&d.requestFullscreen)d.requestFullscreen().then(()=>{if(screen.orientation&&screen.orientation.lock)screen.orientation.lock('landscape').catch(()=>{})}).catch(()=>{})}catch(x){}
},{passive:true});
</script>
"""
mapdir=os.path.join(os.path.dirname(os.path.abspath(__file__)),'public','maps')
maps=sorted(f for f in os.listdir(mapdir) if f.endswith('.js')) if os.path.isdir(mapdir) else []
head+=''.join('<script src="maps/%s"></script>\n'%f for f in maps)
print('mappe reali incluse:',maps or 'nessuna (uso la Rimini schematica)')
out=os.path.join(os.path.dirname(__file__),'public','index.html')
open(out,'w',encoding='utf-8').write(head+s+tail)
print('scritto',out,len(s)//1024,'KB')
