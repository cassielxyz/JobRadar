import {NextResponse} from 'next/server';
import {admin} from '@/lib/supabase';
import {getAuthorizedUser} from '@/lib/auth';
import {extractResumeText,parseResumeDeterministic,enrichResumeWithGemini} from '@/lib/resume-parser';

export const runtime='nodejs';
const MAX=10*1024*1024;
const okTypes=new Set(['application/pdf','application/vnd.openxmlformats-officedocument.wordprocessingml.document','text/plain']);
const safe=(s:string)=>s.replace(/[^a-zA-Z0-9._-]+/g,'-').slice(0,100);

async function auth(){const a=await getAuthorizedUser();return a.status===200?a:null}

export async function GET(){
 const a=await auth(); if(!a)return NextResponse.json({error:'Unauthorized'},{status:401});
 const {data,error}=await admin().from('resumes').select('id,name,original_filename,mime_type,size_bytes,parsed_json,skills,target_roles,certifications,education,experience_years,is_active,created_at,updated_at').eq('user_id',a.user!.id).order('created_at',{ascending:false});
 return NextResponse.json(error?{error:error.message}:data,{status:error?500:200});
}

export async function POST(req:Request){
 const a=await auth(); if(!a)return NextResponse.json({error:'Unauthorized'},{status:401});
 const fd=await req.formData(); const file=fd.get('file'); const label=String(fd.get('name')||'').trim();
 if(!(file instanceof File))return NextResponse.json({error:'Resume file is required.'},{status:400});
 if(file.size<=0||file.size>MAX)return NextResponse.json({error:'Resume must be between 1 byte and 10 MB.'},{status:400});
 const ext=file.name.toLowerCase(); if(!okTypes.has(file.type)&&!(/\.(pdf|docx|txt)$/.test(ext)))return NextResponse.json({error:'Upload PDF, DOCX or TXT.'},{status:400});
 let text=''; try{text=await extractResumeText(file)}catch(e:any){return NextResponse.json({error:e?.message||'Could not read resume.'},{status:400})}
 if(text.length<80)return NextResponse.json({error:'Very little selectable text was found. Use a text-based PDF/DOCX rather than a scanned image resume.'},{status:400});
 let parsed=parseResumeDeterministic(text); parsed=await enrichResumeWithGemini(text,parsed);
 const id=crypto.randomUUID(); const path=`${a.user!.id}/${id}-${safe(file.name)}`; const bytes=Buffer.from(await file.arrayBuffer());
 const up=await admin().storage.from('resumes').upload(path,bytes,{contentType:file.type||'application/octet-stream',upsert:false});
 if(up.error)return NextResponse.json({error:up.error.message},{status:500});
 const current=await admin().from('resumes').select('id').eq('user_id',a.user!.id).eq('is_active',true).maybeSingle(); const makeActive=!current.data;
 const row={id,user_id:a.user!.id,name:label||file.name.replace(/\.[^.]+$/,''),original_filename:file.name,storage_path:path,mime_type:file.type||'application/octet-stream',size_bytes:file.size,raw_text:text.slice(0,50000),parsed_json:parsed,skills:parsed.skills||[],target_roles:parsed.target_roles||[],certifications:parsed.certifications||[],education:parsed.education||[],experience_years:parsed.experience_years,is_active:makeActive};
 const {data,error}=await admin().from('resumes').insert(row).select().single();
 if(error){await admin().storage.from('resumes').remove([path]);return NextResponse.json({error:error.message},{status:500})}
 if(makeActive)await admin().from('candidate_preferences').upsert({user_id:a.user!.id,active_resume_id:id,updated_at:new Date().toISOString()},{onConflict:'user_id'});
 return NextResponse.json(data,{status:201});
}

export async function PATCH(req:Request){
 const a=await auth(); if(!a)return NextResponse.json({error:'Unauthorized'},{status:401});
 const body=await req.json(); const id=String(body.id||''); if(!id)return NextResponse.json({error:'id required'},{status:400});
 const owned=await admin().from('resumes').select('id').eq('id',id).eq('user_id',a.user!.id).maybeSingle(); if(!owned.data)return NextResponse.json({error:'Resume not found'},{status:404});
 if(body.is_active===true){await admin().from('resumes').update({is_active:false,updated_at:new Date().toISOString()}).eq('user_id',a.user!.id);await admin().from('candidate_preferences').upsert({user_id:a.user!.id,active_resume_id:id,updated_at:new Date().toISOString()},{onConflict:'user_id'});}
 const changes:any={updated_at:new Date().toISOString()}; if(typeof body.name==='string'&&body.name.trim())changes.name=body.name.trim(); if(typeof body.is_active==='boolean')changes.is_active=body.is_active;
 const {data,error}=await admin().from('resumes').update(changes).eq('id',id).eq('user_id',a.user!.id).select().single(); return NextResponse.json(error?{error:error.message}:data,{status:error?400:200});
}

export async function DELETE(req:Request){
 const a=await auth(); if(!a)return NextResponse.json({error:'Unauthorized'},{status:401});
 const id=new URL(req.url).searchParams.get('id'); if(!id)return NextResponse.json({error:'id required'},{status:400});
 const {data}=await admin().from('resumes').select('storage_path,is_active').eq('id',id).eq('user_id',a.user!.id).maybeSingle(); if(!data)return NextResponse.json({error:'Resume not found'},{status:404});
 await admin().storage.from('resumes').remove([data.storage_path]); const {error}=await admin().from('resumes').delete().eq('id',id).eq('user_id',a.user!.id);
 if(data.is_active){const next=await admin().from('resumes').select('id').eq('user_id',a.user!.id).order('created_at',{ascending:false}).limit(1).maybeSingle(); if(next.data){await admin().from('resumes').update({is_active:true}).eq('id',next.data.id);await admin().from('candidate_preferences').upsert({user_id:a.user!.id,active_resume_id:next.data.id,updated_at:new Date().toISOString()},{onConflict:'user_id'});}else await admin().from('candidate_preferences').upsert({user_id:a.user!.id,active_resume_id:null,updated_at:new Date().toISOString()},{onConflict:'user_id'});}
 return NextResponse.json(error?{error:error.message}:{ok:true},{status:error?500:200});
}
