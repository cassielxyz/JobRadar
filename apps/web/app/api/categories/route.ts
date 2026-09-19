import {NextResponse} from 'next/server';
import {admin} from '@/lib/supabase';
import {getAuthorizedUser} from '@/lib/auth';
import {dispatchWorkflow} from '@/lib/github-actions';

const allowed=['name','slug','enabled','type','fresher_only','role_keywords','hidden_keywords','exclude_keywords','locations','max_experience_years','salary_min_monthly','salary_max_monthly','stipend_min_monthly','stipend_max_monthly','require_paid','require_official_verification','source_kinds','alert_threshold'] as const;

async function auth(){
  const a=await getAuthorizedUser();
  return a.status===200?a:null;
}

function clean(body:any){
  const out:any={};
  for(const k of allowed)if(k in (body||{}))out[k]=body[k];
  if(out.alert_threshold!=null)out.alert_threshold=Math.max(0,Math.min(100,Number(out.alert_threshold)));
  if(out.max_experience_years!=null)out.max_experience_years=Math.max(0,Math.min(50,Number(out.max_experience_years)));
  for(const k of ['role_keywords','hidden_keywords','exclude_keywords','locations','source_kinds']){
    if(k in out)out[k]=Array.isArray(out[k])?out[k].map((x:any)=>String(x).trim()).filter(Boolean).slice(0,80):[];
  }
  return out;
}

async function queueResearch(enabled=true){
  if(!enabled)return {ok:false,skipped:true};
  try{
    return await dispatchWorkflow('research.yml',{});
  }catch{
    return {ok:false,status:500,error:'Could not queue research.'};
  }
}

export async function GET(){
  const a=await auth();
  if(!a)return NextResponse.json({error:'Unauthorized'},{status:401});
  const {data,error}=await admin().from('categories').select('*').order('created_at');
  return NextResponse.json(error?{error:error.message}:data,{status:error?500:200});
}

export async function POST(req:Request){
  const a=await auth();
  if(!a)return NextResponse.json({error:'Unauthorized'},{status:401});
  const body=clean(await req.json());
  if(!body.name||!body.slug||!body.type)return NextResponse.json({error:'Name, slug and type are required.'},{status:400});
  const {data,error}=await admin().from('categories').insert(body).select().single();
  if(error)return NextResponse.json({error:error.message},{status:400});
  const research=await queueResearch(data?.enabled!==false);
  return NextResponse.json({...data,research_queued:!!research.ok,research_error:research.ok?null:(research as any).error||null},{status:201});
}

export async function PATCH(req:Request){
  const a=await auth();
  if(!a)return NextResponse.json({error:'Unauthorized'},{status:401});
  const raw=await req.json();
  const id=String(raw?.id||'');
  if(!id)return NextResponse.json({error:'Category id is required.'},{status:400});
  const changes=clean(raw);
  delete changes.slug;
  const {data,error}=await admin().from('categories').update({...changes,updated_at:new Date().toISOString()}).eq('id',id).select().single();
  if(error)return NextResponse.json({error:error.message},{status:400});
  const research=await queueResearch(data?.enabled!==false);
  return NextResponse.json({...data,research_queued:!!research.ok,research_error:research.ok?null:(research as any).error||null},{status:200});
}
