import {NextResponse} from 'next/server';
import {admin} from '@/lib/supabase';
import {getAuthorizedUser} from '@/lib/auth';
import {dispatchWorkflow} from '@/lib/github-actions';

export async function POST(req:Request){
  const a=await getAuthorizedUser();
  if(a.status!==200)return NextResponse.json({error:a.status===403?'Forbidden':'Unauthorized'},{status:a.status});
  const body=await req.json().catch(()=>({}));
  const id=String(body?.id||'').trim();
  if(!id)return NextResponse.json({error:'Resume id is required.'},{status:400});
  const {data,error}=await admin().from('resumes').select('id').eq('id',id).eq('user_id',a.user!.id).maybeSingle();
  if(error)return NextResponse.json({error:error.message},{status:500});
  if(!data)return NextResponse.json({error:'Resume not found.'},{status:404});
  const dispatched=await dispatchWorkflow('resume-enrich.yml',{resume_id:id});
  return NextResponse.json(dispatched,{status:dispatched.ok?202:dispatched.status||500});
}
