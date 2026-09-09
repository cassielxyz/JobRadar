import {NextResponse} from 'next/server';import {admin} from '@/lib/supabase';import {getAuthorizedUser} from '@/lib/auth';
export async function GET(req:Request){
 const auth=await getAuthorizedUser();if(auth.status!==200)return NextResponse.json({error:'Unauthorized'},{status:auth.status});
 const u=new URL(req.url);const cat=u.searchParams.get('category_id');
 let q=admin().from('job_matches').select('*,category:categories(id,name,slug,alert_threshold),job:jobs(*)')
    .eq('eligible',true).order('score',{ascending:false}).limit(250);
 if(cat) q=q.eq('category_id',cat);
 const {data,error}=await q;
 if(error) return NextResponse.json({error:error.message},{status:500});
 const filtered=(data||[]).filter((m:any)=>m.job?.active!==false && m.job?.application_status!=='closed');
 return NextResponse.json(filtered);
}
