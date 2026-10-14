import React from 'react';
import { createRoot } from 'react-dom/client';
import App from './ui/App.jsx';
import './ui/styles.css';
import './ui/reference.css';
import './ui/enhancements.css';

createRoot(document.getElementById('root')).render(<App />);
