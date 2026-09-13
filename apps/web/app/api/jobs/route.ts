import {NextResponse} from 'next/server';
import {admin} from '@/lib/supabase';
import {getAuthorizedUser} from '@/lib/auth';
import {assessJobTrust} from '@/lib/job-trust';

const PER_CATEGORY_TARGET=10;
export async function GET(req:Request){
  const auth=await getAuthorizedUser();if(auth.status!==200)return NextResponse.json({error:'Unauthorized'},{status:auth.status});
  const u=new URL(req.url);const cat=u.searchParams.get('category_id');
  let q=admin().from('job_matches').select('*,category:categories(id,name,slug,type,alert_threshold,fresher_only),job:jobs(*)').eq('eligible',true).order('score',{ascending:false}).limit(cat?200:1200);
  if(cat)q=q.eq('category_id',cat);
  const {data,error}=await q;if(error)return NextResponse.json({error:error.message},{status:500});
  const live=(data||[]).flatMap((m:any)=>{
    if(m.job?.active===false||m.job?.application_status==='closed')return [];
    const trust=assessJobTrust(m.job,m.category?.type||'');
    if(trust.blocked||trust.score<55)return [];
    return [{...m,job:{...m.job,trust_score:trust.score,trust_reasons:trust.reasons}}];
  });
  if(cat)return NextResponse.json(live.slice(0,50));
  const grouped=new Map<string,any[]>();
  for(const row of live){const key=String(row.category_id||row.category?.id||'uncategorized');const bucket=grouped.get(key)||[];if(bucket.length<PER_CATEGORY_TARGET)bucket.push(row);grouped.set(key,bucket)}
  const balanced=Array.from(grouped.values()).flat();balanced.sort((a:any,b:any)=>Number(b.score||0)-Number(a.score||0));return NextResponse.json(balanced);
}
