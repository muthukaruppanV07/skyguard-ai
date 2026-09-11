import React from 'react';
import ReactDOM from 'react-dom/client';
import { HashRouter } from 'react-router-dom';
import App from './App';
import { PresentationProvider } from './presentation';
import { ThemeProvider } from './theme';
import './index.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ThemeProvider>
      <PresentationProvider>
        <HashRouter>
          <App />
        </HashRouter>
      </PresentationProvider>
    </ThemeProvider>
  </React.StrictMode>,
);
