import {createRoot} from 'react-dom/client';
import PreviewSession from './PreviewSession';
import {previewConfig} from './previewConfig';
import './studio.css';
// An isolated deployment must supply the /api reverse proxy at this same origin.
// This entry never imports the development bridge, test harness or a service token.
const config=previewConfig({apiBase:'/api',label:'ISOLATED PREVIEW - NOT PRODUCTION'});
createRoot(document.getElementById('root')!).render(<PreviewSession config={config}/>);
