'use client';

import {useEffect,useRef,useState} from 'react';

type Toast={kind:'ok'|'error';title:string;detail:string}|null;

export default function DashboardUX(){
  const [toast,setToast]=useState<Toast>(null);
  const lastNotice=useRef('');
  const detailedErrorAt=useRef(0);
  const closeTimer=useRef<number|undefined>(undefined);
  const hideTimer=useRef<number|undefined>(undefined);

  useEffect(()=>{
    const clearTimers=()=>{
      if(closeTimer.current)window.clearTimeout(closeTimer.current);
      if(hideTimer.current)window.clearTimeout(hideTimer.current);
    };
    const showError=(detail:string)=>{
      clearTimers();
      detailedErrorAt.current=Date.now();
      document.body.dataset.jobradarSync='error';
      setToast({kind:'error',title:'Check this setting',detail});
      hideTimer.current=window.setTimeout(()=>{
        setToast(null);
        delete document.body.dataset.jobradarSync;
      },7000);
    };

    const originalFetch=window.fetch.bind(window);
    window.fetch=(async(input:RequestInfo|URL,init?:RequestInit)=>{
      const response=await originalFetch(input,init);
      const url=typeof input==='string'?input:input instanceof URL?input.toString():input.url;
      if(url.includes('/api/integrations')&&(init?.method||'GET').toUpperCase()==='PATCH'&&!response.ok){
        response.clone().json().then((body:any)=>showError(String(body?.error||'Integration credentials could not be saved.'))).catch(()=>showError('Integration credentials could not be saved.'));
      }
      return response;
    }) as typeof window.fetch;

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

      if((text.includes('could not be saved')||text.includes('failed'))&&Date.now()-detailedErrorAt.current>1500){
        showError(text);
      }
    };

    inspect();
    const observer=new MutationObserver(inspect);
    observer.observe(document.body,{subtree:true,childList:true,characterData:true});
    return()=>{
      window.fetch=originalFetch;
      observer.disconnect();
      clearTimers();
      delete document.body.dataset.jobradarSync;
    };
  },[]);

  if(!toast)return null;
  return <div className={`syncToast ${toast.kind}`} role="status" aria-live="polite">
    <span className="syncToastIcon" aria-hidden>{toast.kind==='ok'?'✓':'!'}</span>
    <span className="syncToastCopy"><strong>{toast.title}</strong><small>{toast.detail}</small></span>
  </div>;
}
