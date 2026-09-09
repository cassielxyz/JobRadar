import './globals.css';
import type {Metadata,Viewport} from 'next';

export const metadata:Metadata={
  title:{default:'JobRadar South',template:'%s · JobRadar South'},
  description:'Resume-driven fresher job research dashboard for networking, cybersecurity and cloud infrastructure.',
  applicationName:'JobRadar South',
  manifest:'/manifest.webmanifest',
  icons:{icon:[{url:'/icon.svg',type:'image/svg+xml'}]},
};
export const viewport:Viewport={themeColor:'#15171a',colorScheme:'light'};
export default function RootLayout({children}:{children:React.ReactNode}){return <html lang="en"><body>{children}</body></html>}
