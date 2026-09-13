export type LearningResource={title:string;url:string;provider:string;free:boolean};
export type LearningItem={skill:string;why:string;resources:LearningResource[]};

const R:{test:(s:string)=>boolean;resources:LearningResource[]}[]=[
  {test:s=>/routing|switching|vlan|tcp\/ip|ccna|cisco|ospf|bgp|network/.test(s),resources:[{title:'Cisco Skills for All',url:'https://skillsforall.com/',provider:'Cisco',free:true}]},
  {test:s=>/windows server|active directory|dns|dhcp|powershell/.test(s),resources:[{title:'Windows Server Network Infrastructure',url:'https://learn.microsoft.com/en-us/training/paths/windows-server-network-infrastructure/',provider:'Microsoft Learn',free:true},{title:'Introduction to AD DS',url:'https://learn.microsoft.com/en-us/training/modules/introduction-to-ad-ds/',provider:'Microsoft Learn',free:true}]},
  {test:s=>/azure|vnet|entra/.test(s),resources:[{title:'Azure learning paths',url:'https://learn.microsoft.com/en-us/training/azure/',provider:'Microsoft Learn',free:true}]},
  {test:s=>/aws|vpc|cloud/.test(s),resources:[{title:'AWS Skill Builder — free digital training',url:'https://aws.amazon.com/training/digital/',provider:'AWS',free:true}]},
  {test:s=>/web security|burp|owasp|sql injection|xss|csrf|api security/.test(s),resources:[{title:'Web Security Academy',url:'https://portswigger.net/web-security',provider:'PortSwigger',free:true}]},
  {test:s=>/python/.test(s),resources:[{title:'Python Tutorial',url:'https://docs.python.org/3/tutorial/',provider:'Python',free:true},{title:'freeCodeCamp Python',url:'https://www.freecodecamp.org/news/tag/python/',provider:'freeCodeCamp',free:true}]},
  {test:s=>/javascript|typescript|html|css/.test(s),resources:[{title:'MDN Learn Web Development',url:'https://developer.mozilla.org/en-US/docs/Learn_web_development',provider:'MDN',free:true}]},
  {test:s=>/react|next\.?js/.test(s),resources:[{title:'React Learn',url:'https://react.dev/learn',provider:'React',free:true},{title:'Next.js Learn',url:'https://nextjs.org/learn',provider:'Next.js',free:true}]},
  {test:s=>/docker|container/.test(s),resources:[{title:'Docker Get Started',url:'https://docs.docker.com/get-started/',provider:'Docker',free:true}]},
  {test:s=>/kubernetes|k8s/.test(s),resources:[{title:'Kubernetes Tutorials',url:'https://kubernetes.io/docs/tutorials/',provider:'Kubernetes',free:true}]},
  {test:s=>/terraform/.test(s),resources:[{title:'Terraform Tutorials',url:'https://developer.hashicorp.com/terraform/tutorials',provider:'HashiCorp',free:true}]},
  {test:s=>/git|github/.test(s),resources:[{title:'GitHub Skills',url:'https://skills.github.com/',provider:'GitHub',free:true}]},
  {test:s=>/linux|bash/.test(s),resources:[{title:'Linux Journey',url:'https://linuxjourney.com/',provider:'Linux Journey',free:true}]},
  {test:s=>/sql|postgres|mysql|database/.test(s),resources:[{title:'SQLBolt',url:'https://sqlbolt.com/',provider:'SQLBolt',free:true}]},
  {test:s=>/soc|siem|incident response|security operations/.test(s),resources:[{title:'Web Security Academy',url:'https://portswigger.net/web-security',provider:'PortSwigger',free:true},{title:'Microsoft Security learning',url:'https://learn.microsoft.com/en-us/training/security/',provider:'Microsoft Learn',free:true}]},
];

export function resourcesForSkill(skill:string){
  const s=skill.toLowerCase();
  const found:LearningResource[]=[];
  for(const row of R)if(row.test(s))for(const item of row.resources)if(!found.some(x=>x.url===item.url))found.push(item);
  if(found.length)return found.slice(0,3);
  return [{title:'freeCodeCamp learning library',url:'https://www.freecodecamp.org/news/',provider:'freeCodeCamp',free:true}];
}

export function makeLearningPlan(skills:string[],jobTitle=''){return Array.from(new Set(skills.map(s=>s.trim()).filter(Boolean))).slice(0,12).map(skill=>({skill,why:`Requested or strongly implied by ${jobTitle||'the job description'} but not verified in your active resume.`,resources:resourcesForSkill(skill)}));}
