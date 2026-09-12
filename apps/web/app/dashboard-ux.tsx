'use client';

import {useEffect,useRef,useState} from 'react';

type Toast={kind:'ok'|'error';title:string;detail:string}|null;

export default function DashboardUX(){
  const [toast,setToast]=useState<Toast>(null);
  const lastNotice=useRef('');
  const closeTimer=useRef<number|undefined>(undefined);
  const hideTimer=useRef<number|undefined>(undefined);

  useEffect(()=>{
    const clearTimers=()=>{
      if(closeTimer.current)window.clearTimeout(closeTimer.current);
      if(hideTimer.current)window.clearTimeout(hideTimer.current);
    };
    const inspect=()=>{
      const text=(document.querySelector('.flash')?.textContent||'').trim();
      if(!text||text===lastNotice.current)return;
      lastNotice.current=text;

      if(text.startsWith('Changes saved and synced.')){
        clearTimers();
        document.body.dataset.jobradarSync='saved';
        setToast({kind:'ok',title:'Saved & synced',detail:'Your dashboard settings are stored in Supabase and ready for the next research run.'});
        closeTimer.current=window.setTimeout(()=>{
          const close=document.querySelector<HTMLButtonElement>('.settingsDrawer .close');
          close?.click();
          window.scrollTo({top:0,behavior:'smooth'});
          delete document.body.dataset.jobradarSync;
        },1050);
        hideTimer.current=window.setTimeout(()=>setToast(null),3000);
        return;
      }

      if(text.includes('could not be saved')||text.includes('failed')){
        clearTimers();
        document.body.dataset.jobradarSync='error';
        setToast({kind:'error',title:'Not fully saved',detail:text});
        hideTimer.current=window.setTimeout(()=>{
          setToast(null);
          delete document.body.dataset.jobradarSync;
        },6000);
      }
    };

    inspect();
    const observer=new MutationObserver(inspect);
    observer.observe(document.body,{subtree:true,childList:true,characterData:true});
    return()=>{observer.disconnect();clearTimers();delete document.body.dataset.jobradarSync};
  },[]);

  if(!toast)return null;
  return <div className={`syncToast ${toast.kind}`} role="status" aria-live="polite">
    <span className="syncToastIcon" aria-hidden>{toast.kind==='ok'?'✓':'!'}</span>
    <span className="syncToastCopy"><strong>{toast.title}</strong><small>{toast.detail}</small></span>
  </div>;
}
