import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import App from './App.jsx';

// React 18 createRoot API — mount the app inside BrowserRouter so that
// react-router-dom hooks (useNavigate, useLocation, etc.) are available
// everywhere in the component tree.
ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>
);
