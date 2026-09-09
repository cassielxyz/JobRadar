import {NextRequest,NextResponse} from 'next/server';
import {createServerSupabase} from '@/lib/supabase-server';
import {emailIsAuthorized} from '@/lib/auth';

export async function GET(request:NextRequest){
  const code=request.nextUrl.searchParams.get('code');
  const next=request.nextUrl.searchParams.get('next')||'/';
  const supabase=createServerSupabase();
  if(code){
    const {error}=await supabase.auth.exchangeCodeForSession(code);
    if(!error){
      const {data:{user}}=await supabase.auth.getUser();
      if(user && emailIsAuthorized(user.email)) return NextResponse.redirect(new URL(next,request.url));
      await supabase.auth.signOut();
      return NextResponse.redirect(new URL('/unauthorized',request.url));
    }
  }
  return NextResponse.redirect(new URL('/login?error=oauth_callback',request.url));
}
