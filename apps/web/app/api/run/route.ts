import {NextResponse} from 'next/server';
import {getAuthorizedUser} from '@/lib/auth';

export async function POST(req:Request){
  const a=await getAuthorizedUser();
  if(a.status!==200) return NextResponse.json({error:a.status===403?'Forbidden':'Unauthorized'},{status:a.status});
  const repo=process.env.GITHUB_REPOSITORY, token=process.env.GITHUB_DISPATCH_TOKEN;
  if(!repo||!token) return NextResponse.json({error:'Configure GITHUB_REPOSITORY and GITHUB_DISPATCH_TOKEN in Vercel.'},{status:400});
  let mode='research';
  try{const body=await req.json(); if(body?.mode==='test-notifications') mode='test-notifications';}catch{}
  const r=await fetch(`https://api.github.com/repos/${repo}/actions/workflows/research.yml/dispatches`,{
    method:'POST',
    headers:{Authorization:`Bearer ${token}`,Accept:'application/vnd.github+json','Content-Type':'application/json'},
    body:JSON.stringify({ref:'main',inputs:{mode}})
  });
  if(!r.ok){
    const text=(await r.text()).slice(0,500);
    return NextResponse.json({ok:false,error:text||`GitHub returned ${r.status}`},{status:500});
  }
  return NextResponse.json({ok:true,mode});
}
