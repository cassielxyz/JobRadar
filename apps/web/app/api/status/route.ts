import {NextResponse} from 'next/server';
import {admin} from '@/lib/supabase';
import {getAuthorizedUser} from '@/lib/auth';

export async function GET(){
  const a=await getAuthorizedUser();
  if(a.status!==200) return NextResponse.json({error:a.status===403?'Forbidden':'Unauthorized'},{status:a.status});
  const {data,error}=await admin().from('research_runs')
    .select('id,trigger,started_at,finished_at,status,discovered,verified,matched,alerted,errors,notification_status')
    .order('started_at',{ascending:false}).limit(1).maybeSingle();
  return NextResponse.json(error?{error:error.message}:data,{status:error?500:200});
}
