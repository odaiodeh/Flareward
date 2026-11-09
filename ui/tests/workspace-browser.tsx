/** Full production App; external identity/settings route to the owned browser fixture. */
import React from 'react';
import { createRoot } from 'react-dom/client';
import { QueryClientProvider } from '@tanstack/react-query';
import App from '../client/src/App';
import axios from '../client/src/http/axiosAgentConfig';
import { api as authApi } from '../client/src/http/authClient';
import { queryClient } from '../client/src/http/queryClient';
import { TooltipProvider } from '../client/src/components/ui/tooltip';
import '../client/src/index.css';

axios.defaults.baseURL = '/api';
authApi.defaults.baseURL = '/fixture';

createRoot(document.getElementById('root')!).render(
  <QueryClientProvider client={queryClient}><TooltipProvider><App /></TooltipProvider></QueryClientProvider>,
);
