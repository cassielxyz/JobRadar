import './globals.css';
import './v09.css';
import type {Metadata,Viewport} from 'next';

export const metadata:Metadata={
  title:{default:'JobRadar Everywhere',template:'%s · JobRadar Everywhere'},
  description:'Resume-driven verified job discovery, fresher filtering, application tracking and alerts across company careers, ATS boards, startups and public-sector sources.',
  applicationName:'JobRadar Everywhere',
  manifest:'/manifest.webmanifest',
  icons:{icon:[{url:'/icon.svg',type:'image/svg+xml'}]},
};
export const viewport:Viewport={themeColor:'#15171a',colorScheme:'light'};
export default function RootLayout({children}:{children:React.ReactNode}){return <html lang="en"><body>{children}</body></html>}
