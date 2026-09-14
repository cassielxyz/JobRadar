import {NextResponse} from 'next/server';
import {admin} from '@/lib/supabase';
import {getAuthorizedUser} from '@/lib/auth';
import {decryptIntegrations} from '@/lib/integration-crypto';
import {buildTailoredResume} from '@/lib/resume-studio';

const safeArr=(v:any)=>Array.isArray(v)?v.map(x=>String(x).trim()).filter(Boolean):[];
const norm=(s:any)=>String(s||'').toLowerCase().replace(/\s+/g,' ').trim();
const allowedSkill=(candidate:string,verified:string[])=>verified.some(v=>{const a=norm(v),b=norm(candidate);return a===b||a.includes(b)||b.includes(a)});
const schemaError=(message?:string)=>String(message||'').includes('generated_resumes')||String(message||'').includes('schema cache');
const migrationResponse=(message?:string)=>NextResponse.json({error:'Resume Studio database is not initialized. Run Supabase migration 009_trust_resume_studio.sql, then refresh the dashboard.',migration_required:'009_trust_resume_studio.sql',detail:message||''},{status:503});

async function auth(){const a=await getAuthorizedUser();return a.status===200?a:null}
async function enrichRow(row:any){if(!row)return row;const [job,resume]=await Promise.all([admin().from('jobs').select('id,title,company,apply_url,source_url,canonical_url').eq('id',row.job_id).maybeSingle(),admin().from('resumes').select('id,name').eq('id',row.base_resume_id).maybeSingle()]);return {...row,job:job.data||null,base_resume:resume.data||null}}

export async function GET(){const a=await auth();if(!a)return NextResponse.json({error:'Unauthorized'},{status:401});const {data,error}=await admin().from('generated_resumes').select('*').eq('user_id',a.user!.id).order('updated_at',{ascending:false});if(error)return schemaError(error.message)?migrationResponse(error.message):NextResponse.json({error:error.message},{status:500});return NextResponse.json(await Promise.all((data||[]).map(enrichRow)))}

export async function POST(req:Request){
  const a=await auth();if(!a)return NextResponse.json({error:'Unauthorized'},{status:401});
  const body=await req.json().catch(()=>({}));const jobId=String(body.job_id||'');if(!jobId)return NextResponse.json({error:'job_id required'},{status:400});
  const {data:job,error:je}=await admin().from('jobs').select('*').eq('id',jobId).maybeSingle();if(je||!job)return NextResponse.json({error:je?.message||'Job not found'},{status:404});
  const {data:pref}=await admin().from('candidate_preferences').select('*').eq('user_id',a.user!.id).maybeSingle();const rid=String(body.base_resume_id||pref?.active_resume_id||'');if(!rid)return NextResponse.json({error:'Choose an active resume first.'},{status:400});
  const {data:resume,error:re}=await admin().from('resumes').select('*').eq('id',rid).eq('user_id',a.user!.id).maybeSingle();if(re||!resume)return NextResponse.json({error:re?.message||'Resume not found'},{status:404});
  const {data:match}=await admin().from('job_matches').select('score,resume_score,skill_gaps,reasons,resume_reasons').eq('job_id',jobId).order('score',{ascending:false}).limit(1).maybeSingle();
  let integrations:any={};const {data:intRow}=await admin().from('integration_settings').select('encrypted_payload').eq('user_id',a.user!.id).maybeSingle();if(intRow?.encrypted_payload){try{integrations=decryptIntegrations(intRow.encrypted_payload)}catch{}}
  const built=await buildTailoredResume(job,resume,match||{},integrations.gemini_api_key||process.env.GEMINI_API_KEY||'',integrations.gemini_model||process.env.GEMINI_MODEL||'gemini-3.1-flash-lite');
  const payload={user_id:a.user!.id,job_id:jobId,base_resume_id:rid,title:`${job.title} — ${job.company}`,content_json:built.content,learning_plan:built.learning_plan,ats_score:built.ats_score,provider:built.provider,status:'draft',updated_at:new Date().toISOString()};
  const {data,error}=await admin().from('generated_resumes').upsert(payload,{onConflict:'user_id,job_id,base_resume_id'}).select().single();if(error)return schemaError(error.message)?migrationResponse(error.message):NextResponse.json({error:error.message},{status:400});return NextResponse.json(await enrichRow(data),{status:201});
}

export async function PATCH(req:Request){
  const a=await auth();if(!a)return NextResponse.json({error:'Unauthorized'},{status:401});const body=await req.json().catch(()=>({}));const id=String(body.id||'');if(!id)return NextResponse.json({error:'id required'},{status:400});
  const {data:existing,error:ee}=await admin().from('generated_resumes').select('*').eq('id',id).eq('user_id',a.user!.id).maybeSingle();if(ee&&schemaError(ee.message))return migrationResponse(ee.message);if(!existing)return NextResponse.json({error:'Generated resume not found'},{status:404});
  const {data:base}=await admin().from('resumes').select('skills').eq('id',existing.base_resume_id).eq('user_id',a.user!.id).maybeSingle();const verified=safeArr(base?.skills);
  const incoming={...(body.content_json||{})};if('skills'in incoming)incoming.skills=safeArr(incoming.skills).filter((x:string)=>allowedSkill(x,verified));if('learning_skills'in incoming)incoming.learning_skills=safeArr(incoming.learning_skills);if('missing_skills'in incoming)incoming.missing_skills=safeArr(incoming.missing_skills);
  const clean={...existing.content_json,...incoming};const {data,error}=await admin().from('generated_resumes').update({content_json:clean,status:'edited',updated_at:new Date().toISOString()}).eq('id',id).eq('user_id',a.user!.id).select().single();return NextResponse.json(error?{error:error.message}:await enrichRow(data),{status:error?400:200});
}

export async function DELETE(req:Request){const a=await auth();if(!a)return NextResponse.json({error:'Unauthorized'},{status:401});const id=new URL(req.url).searchParams.get('id');if(!id)return NextResponse.json({error:'id required'},{status:400});const {error}=await admin().from('generated_resumes').delete().eq('id',id).eq('user_id',a.user!.id);if(error&&schemaError(error.message))return migrationResponse(error.message);return NextResponse.json(error?{error:error.message}:{ok:true},{status:error?500:200})}
