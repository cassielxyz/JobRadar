import {NextResponse} from 'next/server';
import {admin} from '@/lib/supabase';
import {getAuthorizedUser} from '@/lib/auth';
export async function GET(req:Request){const a=await getAuthorizedUser();if(a.status!==200)return NextResponse.json({error:a.status===403?'Forbidden':'Unauthorized'},{status:a.status});const u=new URL(req.url);const cat=u.searchParams.get('category');let q=admin().from('job_matches').select('score,reasons,eligible,alerted_at,ai_review,category:categories(id,name,slug),job:jobs(*)').eq('eligible',true).order('score',{ascending:false}).limit(250);if(cat)q=q.eq('category_id',cat);const {data,error}=await q;return NextResponse.json(error?{error:error.message}:data,{status:error?500:200});}
