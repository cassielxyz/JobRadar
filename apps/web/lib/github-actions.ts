export type DispatchResult={ok:boolean;status:number;error?:string;workflowUrl?:string};

export async function dispatchWorkflow(workflow:string,inputs:Record<string,string>={}):Promise<DispatchResult>{
  const repo=(process.env.GITHUB_REPOSITORY||'').trim();
  const token=(process.env.GITHUB_DISPATCH_TOKEN||'').trim();
  if(!repo||!token)return {ok:false,status:400,error:'Configure GITHUB_REPOSITORY and GITHUB_DISPATCH_TOKEN in Vercel.'};
  if(!/^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/.test(repo))return {ok:false,status:400,error:'GITHUB_REPOSITORY must be owner/repository.'};
  const safeWorkflow=workflow.replace(/[^A-Za-z0-9_.-]/g,'');
  const r=await fetch(`https://api.github.com/repos/${repo}/actions/workflows/${safeWorkflow}/dispatches`,{
    method:'POST',
    headers:{Authorization:`Bearer ${token}`,Accept:'application/vnd.github+json','Content-Type':'application/json','X-GitHub-Api-Version':'2022-11-28'},
    body:JSON.stringify({ref:'main',inputs}),
    cache:'no-store',
  });
  if(!r.ok){
    const text=(await r.text()).slice(0,500);
    return {ok:false,status:r.status,error:text||`GitHub returned ${r.status}`};
  }
  return {ok:true,status:r.status,workflowUrl:`https://github.com/${repo}/actions/workflows/${safeWorkflow}`};
}
