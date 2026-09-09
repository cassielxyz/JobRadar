import {NextResponse} from 'next/server';
import {admin} from '@/lib/supabase';
import {getAuthorizedUser} from '@/lib/auth';

export async function GET(){
  const a=await getAuthorizedUser();
  if(a.status!==200)return NextResponse.json({error:'Unauthorized'},{status:a.status});
  const {data,error}=await admin().from('applications')
    .select('*,job:jobs(id,title,company,location,apply_url,notification_url),resume:resumes(id,name)')
    .eq('user_id',a.user!.id).order('created_at',{ascending:false}).limit(200);
  return NextResponse.json(error?{error:error.message}:data,{status:error?500:200});
}

export async function POST(req:Request){
  const a=await getAuthorizedUser();
  if(a.status!==200)return NextResponse.json({error:'Unauthorized'},{status:a.status});
  const b=await req.json();
  if(!b.job_id)return NextResponse.json({error:'job_id required'},{status:400});
  const payload={
    user_id:a.user!.id,job_id:b.job_id,resume_id:b.resume_id||null,
    status:b.status||'saved',method:b.method||'manual',score:b.score??b.score_snapshot??null,
    apply_url:b.apply_url||null,details:b.details||b.answers||{},updated_at:new Date().toISOString()
  };
  const {data,error}=await admin().from('applications').upsert(payload,{onConflict:'user_id,job_id'}).select().single();
  return NextResponse.json(error?{error:error.message}:data,{status:error?400:201});
}

export async function PATCH(req:Request){
  const a=await getAuthorizedUser();
  if(a.status!==200)return NextResponse.json({error:'Unauthorized'},{status:a.status});
  const b=await req.json(); if(!b.id)return NextResponse.json({error:'id required'},{status:400});
  const p:any={updated_at:new Date().toISOString()};
  if('status' in b)p.status=b.status; if('details' in b)p.details=b.details;
  const {data,error}=await admin().from('applications').update(p).eq('id',b.id).eq('user_id',a.user!.id).select().single();
  return NextResponse.json(error?{error:error.message}:data,{status:error?400:200});
}
