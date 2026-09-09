import {createServerClient} from '@supabase/ssr';
import {NextResponse,type NextRequest} from 'next/server';

function isAuthorized(email?: string | null){
  if(!email) return false;
  const allowed=(process.env.AUTHORIZED_EMAILS||'').split(',').map(v=>v.trim().toLowerCase()).filter(Boolean);
  return allowed.includes(email.toLowerCase());
}

export async function middleware(request:NextRequest){
  let response=NextResponse.next({request});
  const url=process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key=process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY || process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if(!url||!key) return response;

  const supabase=createServerClient(url,key,{
    cookies:{
      getAll(){return request.cookies.getAll()},
      setAll(items){
        items.forEach(({name,value})=>request.cookies.set(name,value));
        response=NextResponse.next({request});
        items.forEach(({name,value,options})=>response.cookies.set(name,value,options));
      }
    }
  });

  const {data:{user}}=await supabase.auth.getUser();
  const path=request.nextUrl.pathname;
  const publicPath=path==='/login'||path==='/unauthorized'||path.startsWith('/auth/callback')||path.startsWith('/api/');

  if(!user && !publicPath){
    const login=new URL('/login',request.url);
    login.searchParams.set('next',path);
    return NextResponse.redirect(login);
  }

  if(user && !isAuthorized(user.email) && path!=='/unauthorized' && !path.startsWith('/auth/callback')){
    return NextResponse.redirect(new URL('/unauthorized',request.url));
  }

  if(user && isAuthorized(user.email) && (path==='/login'||path==='/unauthorized')){
    return NextResponse.redirect(new URL('/',request.url));
  }

  return response;
}

export const config={
  matcher:['/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)']
};
