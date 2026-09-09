import {NextResponse} from 'next/server';
import {getAuthorizedUser} from '@/lib/auth';
import {dispatchWorkflow} from '@/lib/github-actions';

export async function POST(req:Request){
  const a=await getAuthorizedUser();
  if(a.status!==200)return NextResponse.json({error:a.status===403?'Forbidden':'Unauthorized'},{status:a.status});
  let mode='research';
  try{const body=await req.json();if(body?.mode==='test-notifications')mode='test-notifications';}catch{}
  const workflow=mode==='test-notifications'?'notification-test.yml':'research.yml';
  const result=await dispatchWorkflow(workflow,{});
  return NextResponse.json({...result,mode},{status:result.ok?202:result.status||500});
}
