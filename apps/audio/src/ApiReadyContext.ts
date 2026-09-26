import {createContext} from 'react';

// Readiness of the shared API connection, independent of model readiness.
export const ApiReadyContext = createContext(false);
