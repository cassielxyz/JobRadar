import type {MetadataRoute} from 'next';
export default function manifest():MetadataRoute.Manifest{return {name:'JobRadar South',short_name:'JobRadar',description:'Resume-driven verified fresher job research',start_url:'/',display:'standalone',background_color:'#f5f6f8',theme_color:'#15171a',icons:[{src:'/icon.svg',sizes:'any',type:'image/svg+xml'}]};}
