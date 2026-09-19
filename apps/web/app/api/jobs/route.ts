import {NextResponse} from 'next/server';
import {admin} from '@/lib/supabase';
import {getAuthorizedUser} from '@/lib/auth';
import {assessJobTrust} from '@/lib/job-trust';

const PER_CATEGORY_TARGET=10;
const HIDDEN_APPLICATION_STATUSES=['queued','review_required','submitted','applied_manual','interview','offer','rejected','withdrawn','skipped'];
const norm=(v:any)=>String(v||'').toLowerCase().replace(/[^a-z0-9]+/g,' ').trim();
const identity=(j:any)=>[norm(j?.title),norm(j?.company),norm(j?.location)].join('|');

export async function GET(req:Request){
  const auth=await getAuthorizedUser();
  if(auth.status!==200)return NextResponse.json({error:'Unauthorized'},{status:auth.status});
  const userId=auth.user!.id;
  const u=new URL(req.url);const cat=u.searchParams.get('category_id');

  const {data:applications}=await admin().from('applications').select('job_id,status').eq('user_id',userId).in('status',HIDDEN_APPLICATION_STATUSES);
  const hiddenJobs=new Set((applications||[]).map((x:any)=>String(x.job_id)));

  let q=admin().from('job_matches').select('*,category:categories(id,name,slug,type,alert_threshold,fresher_only),job:jobs(*)').eq('eligible',true).order('score',{ascending:false}).limit(cat?300:1600);
  if(cat)q=q.eq('category_id',cat);
  const {data,error}=await q;
  if(error)return NextResponse.json({error:error.message},{status:500});

  const live:any[]=[];
  const seenJobs=new Set<string>();
  const seenIdentities=new Set<string>();
  for(const m of data||[]){
    const j=m.job||{};
    const jid=String(j.id||m.job_id||'');
    if(!jid||hiddenJobs.has(jid)||j.active===false||j.application_status==='closed')continue;
    const trust=assessJobTrust(j,m.category?.type||'');
    if(trust.blocked||trust.score<55)continue;
    const key=identity(j);
    if(seenJobs.has(jid)||(key!=='||'&&seenIdentities.has(key)))continue;
    seenJobs.add(jid);if(key!=='||')seenIdentities.add(key);
    live.push({...m,job:{...j,trust_score:trust.score,trust_reasons:trust.reasons}});
  }

  if(cat)return NextResponse.json(live.slice(0,50));
  const grouped=new Map<string,any[]>();
  for(const row of live){
    const key=String(row.category_id||row.category?.id||'uncategorized');
    const bucket=grouped.get(key)||[];
    if(bucket.length<PER_CATEGORY_TARGET)bucket.push(row);
    grouped.set(key,bucket);
  }
  const balanced=Array.from(grouped.values()).flat();
  balanced.sort((a:any,b:any)=>Number(b.score||0)-Number(a.score||0));
  return NextResponse.json(balanced);
}
