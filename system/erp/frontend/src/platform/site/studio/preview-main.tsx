import {createRoot} from 'react-dom/client';
import PreviewSession from './PreviewSession';
import {previewConfig, HOSTED_API} from './previewConfig';
import './studio.css';
// An isolated deployment must supply the /api reverse proxy at this same origin.
// This entry never imports the development bridge, test harness or a service token.
// A hosted build (VITE_STUDIO_API = the production API) signs in with the ERP session (SSO).
const hostedApi=import.meta.env.VITE_STUDIO_API===HOSTED_API;
const config=previewConfig({apiBase:hostedApi?HOSTED_API:'/api',label:hostedApi?'Mizan Studio':'ISOLATED PREVIEW - NOT PRODUCTION'});
createRoot(document.getElementById('root')!).render(<PreviewSession config={config}/>);
