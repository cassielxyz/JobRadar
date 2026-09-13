'use client';

import {useEffect,useMemo,useState} from 'react';
import {createPortal} from 'react-dom';

type AnyObj=Record<string,any>;
type PortalTarget={node:Element;row:AnyObj;key:string};
type Mode='list'|'edit'|'learn';

const norm=(v:any)=>String(v||'').toLowerCase().replace(/\s+/g,' ').trim();
const lines=(v:any)=>Array.isArray(v)?v.join('\n'):'';
const list=(v:string)=>v.split(/\n+/).map(x=>x.trim()).filter(Boolean);
const comma=(v:any)=>Array.isArray(v)?v.join(', '):'';
const commaList=(v:string)=>v.split(',').map(x=>x.trim()).filter(Boolean);

export default function ResumeStudioEnhancer(){
  const [mounted,setMounted]=useState(false);
  const [jobs,setJobs]=useState<AnyObj[]>([]);
  const [generated,setGenerated]=useState<AnyObj[]>([]);
  const [targets,setTargets]=useState<PortalTarget[]>([]);
  const [actionHost,setActionHost]=useState<Element|null>(null);
  const [open,setOpen]=useState(false);
  const [mode,setMode]=useState<Mode>('list');
  const [selected,setSelected]=useState<AnyObj|null>(null);
  const [learning,setLearning]=useState<AnyObj|null>(null);
  const [busy,setBusy]=useState(false);
  const [message,setMessage]=useState('');

  const refreshJobs=async()=>{const r=await fetch('/api/jobs',{cache:'no-store'});const d=await r.json().catch(()=>[]);if(r.ok&&Array.isArray(d))setJobs(d)};
  const refreshGenerated=async()=>{const r=await fetch('/api/generated-resumes',{cache:'no-store'});const d=await r.json().catch(()=>[]);if(r.ok&&Array.isArray(d))setGenerated(d)};

  useEffect(()=>{setMounted(true);refreshJobs();refreshGenerated()},[]);
  useEffect(()=>{
    if(!mounted)return;
    let raf=0;
    const scan=()=>{
      cancelAnimationFrame(raf);raf=requestAnimationFrame(()=>{
        setActionHost(document.querySelector('.top .actions'));
        const next:PortalTarget[]=[];
        document.querySelectorAll('.job').forEach((card,index)=>{
          const title=norm(card.querySelector('h3')?.textContent);
          const company=norm(card.querySelector('.company')?.textContent);
          if(!title)return;
          const row=jobs.find(x=>norm(x?.job?.title)===title&&(!company||norm(x?.job?.company)===company))||jobs.find(x=>norm(x?.job?.title)===title);
          const node=card.querySelector('.links');
          if(row&&node)next.push({node,row,key:String(row?.job?.id||index)});
        });
        setTargets(next);
      });
    };
    scan();
    const ob=new MutationObserver(scan);ob.observe(document.body,{subtree:true,childList:true,characterData:true});
    const timer=window.setInterval(()=>{refreshJobs();refreshGenerated()},45000);
    return()=>{ob.disconnect();cancelAnimationFrame(raf);window.clearInterval(timer)};
  },[mounted,jobs.length]);

  const createResume=async(row:AnyObj)=>{
    const job=row?.job||{};if(!job.id)return;
    setBusy(true);setMessage('Creating a truthful ATS draft from your saved resume and this job description…');
    const r=await fetch('/api/generated-resumes',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({job_id:job.id})});const d=await r.json().catch(()=>({}));setBusy(false);
    if(!r.ok){setMessage(d.error||'Could not create the ATS resume. Run migration 009 and check your active resume.');setOpen(true);return}
    setSelected(d);setMode('edit');setOpen(true);setMessage(d.provider==='gemini'?'ATS draft created with Gemini + integrity filtering.':'ATS draft created with deterministic integrity-safe tailoring.');await refreshGenerated();
  };
  const openLearning=async(row:AnyObj)=>{
    const job=row?.job||{};if(!job.id)return;setBusy(true);setMessage('');
    const r=await fetch(`/api/learning-plan?job_id=${encodeURIComponent(job.id)}`,{cache:'no-store'});const d=await r.json().catch(()=>({}));setBusy(false);setLearning(d);setMode('learn');setOpen(true);if(!r.ok)setMessage(d.error||'Could not build learning plan.');
  };
  const saveDraft=async()=>{
    if(!selected?.id)return;setBusy(true);setMessage('');
    const r=await fetch('/api/generated-resumes',{method:'PATCH',headers:{'content-type':'application/json'},body:JSON.stringify({id:selected.id,content_json:selected.content_json})});const d=await r.json().catch(()=>({}));setBusy(false);
    if(!r.ok){setMessage(d.error||'Could not save draft.');return}setSelected(d);setMessage('Resume changes saved. Skills are restricted to evidence from your uploaded resume.');await refreshGenerated();
  };
  const removeDraft=async(id:string)=>{if(!confirm('Delete this generated resume?'))return;await fetch(`/api/generated-resumes?id=${encodeURIComponent(id)}`,{method:'DELETE'});if(selected?.id===id)setSelected(null);await refreshGenerated();setMode('list')};
  const chooseDraft=(r:AnyObj)=>{setSelected(r);setMode('edit');setOpen(true);setMessage('')};
  const content=selected?.content_json||{};
  const sourceFor=(row:AnyObj)=>row?.job?.source_url||row?.job?.canonical_url||'';

  const drawer=useMemo(()=>open?<div className="resumeStudioOverlay" onClick={()=>setOpen(false)}><section className="resumeStudioDrawer" onClick={e=>e.stopPropagation()}>
    <header className="rsHead"><div><span className="rsKicker">JOBRADAR RESUME STUDIO</span><h2>{mode==='list'?'Created resumes':mode==='learn'?'What to learn':'ATS resume draft'}</h2></div><button className="rsClose" onClick={()=>setOpen(false)} aria-label="Close">×</button></header>
    <div className="rsTabs"><button className={mode==='list'?'active':''} onClick={()=>setMode('list')}>Created resumes</button>{selected&&<button className={mode==='edit'?'active':''} onClick={()=>setMode('edit')}>Edit draft</button>}{learning&&<button className={mode==='learn'?'active':''} onClick={()=>setMode('learn')}>Learning plan</button>}</div>
    {message&&<div className="rsMessage">{message}</div>}
    {busy&&<div className="rsLoading">Working…</div>}

    {mode==='list'&&<div className="rsList">{generated.length===0?<div className="rsEmpty"><b>No generated resumes yet.</b><span>Open any job and choose ATS resume. JobRadar will tailor your existing facts to the job description.</span></div>:generated.map(r=><article className="rsResumeCard" key={r.id}><div className="rsCardTop"><div><b>{r.job?.title||r.title}</b><span>{r.job?.company||''}</span></div><span className="rsScore">ATS {r.ats_score||0}%</span></div><small>Base: {r.base_resume?.name||'Saved resume'} · {r.provider||'rules'} · {r.status}</small><div className="rsCardActions"><button onClick={()=>chooseDraft(r)}>Edit / preview</button><a href={`/api/generated-resumes/${r.id}/docx`}>Download DOCX</a>{r.job?.apply_url&&<a className="primary" href={r.job.apply_url} target="_blank" rel="noreferrer">Apply</a>}<button className="danger" onClick={()=>removeDraft(r.id)}>Delete</button></div></article>)}</div>}

    {mode==='edit'&&selected&&<div className="rsEditor"><div className="rsIntegrity"><b>Integrity guard is ON</b><span>JobRadar may rewrite and reorder facts for ATS clarity, but it will not claim skills, certifications or experience that are missing from your uploaded resume. Missing requirements stay in the learning plan.</span></div><div className="rsMeta"><span>ATS estimate <b>{selected.ats_score||0}%</b></span><span>Provider <b>{selected.provider||'rules'}</b></span><span>Job <b>{selected.job?.title||selected.title}</b></span></div><label>Headline<input value={content.headline||''} onChange={e=>setSelected({...selected,content_json:{...content,headline:e.target.value}})}/></label><label>Professional summary<textarea value={content.summary||''} onChange={e=>setSelected({...selected,content_json:{...content,summary:e.target.value}})}/></label><label>Verified skills<input value={comma(content.skills)} onChange={e=>setSelected({...selected,content_json:{...content,skills:commaList(e.target.value)}})}/><small>Unknown JD skills are removed server-side instead of being falsely added.</small></label><label>Experience bullets<textarea value={lines(content.experience_bullets)} onChange={e=>setSelected({...selected,content_json:{...content,experience_bullets:list(e.target.value)}})}/></label><label>Project bullets<textarea value={lines(content.project_bullets)} onChange={e=>setSelected({...selected,content_json:{...content,project_bullets:list(e.target.value)}})}/></label><label>Education<textarea value={lines(content.education)} onChange={e=>setSelected({...selected,content_json:{...content,education:list(e.target.value)}})}/></label><label>Certifications<textarea value={lines(content.certifications)} onChange={e=>setSelected({...selected,content_json:{...content,certifications:list(e.target.value)}})}/></label>{(content.missing_skills||[]).length>0&&<div className="rsMissing"><b>Not claimed / learn next</b><div>{content.missing_skills.map((x:string)=><span key={x}>{x}</span>)}</div></div>}<div className="rsBottom"><button className="rsSave" disabled={busy} onClick={saveDraft}>Save changes</button><a href={`/api/generated-resumes/${selected.id}/docx`}>Download DOCX</a>{selected.job?.apply_url&&<a href={selected.job.apply_url} target="_blank" rel="noreferrer">Apply to job</a>}<button onClick={async()=>{const fake={job:{id:selected.job_id,title:selected.job?.title,company:selected.job?.company}};await openLearning(fake)}}>What to learn</button></div></div>}

    {mode==='learn'&&<div className="rsLearn"><div className="rsIntegrity"><b>Gap-to-learning plan</b><span>These are requirements found in the job description that are not verified in your active resume. Learn them first, then update your master resume with truthful evidence.</span></div>{!learning?.skills?.length?<div className="rsEmpty"><b>No obvious skill gaps detected.</b><span>Always read the full job description before applying.</span></div>:learning.skills.map((item:AnyObj)=><article className="rsLearnCard" key={item.skill}><h3>{item.skill}</h3><p>{item.why}</p><div>{(item.resources||[]).map((r:AnyObj)=><a key={r.url} href={r.url} target="_blank" rel="noreferrer">{r.title}<small>{r.provider}{r.free?' · free':''}</small></a>)}</div></article>)}</div>}
  </section></div>:null,[open,mode,selected,learning,generated,busy,message]);

  if(!mounted)return null;
  return <>{actionHost&&createPortal(<button className="btn secondary rsHeaderButton" onClick={()=>{setOpen(true);setMode('list');refreshGenerated()}}>Created resumes</button>,actionHost)}{targets.map(({node,row,key})=>createPortal(<><button className="textLink buttonLink rsJobButton" onClick={()=>createResume(row)}>ATS resume</button><button className="textLink buttonLink rsJobButton" onClick={()=>openLearning(row)}>What to learn</button>{sourceFor(row)&&<a className="textLink rsSourceLink" href={sourceFor(row)} target="_blank" rel="noreferrer">View source</a>}{row?.job?.trust_score!=null&&<span className="rsTrustMini" title={(row.job.trust_reasons||[]).join(' · ')}>Trust {row.job.trust_score}%</span>}</>,node,'jr-'+key))}{drawer&&createPortal(drawer,document.body)}</>;
}
