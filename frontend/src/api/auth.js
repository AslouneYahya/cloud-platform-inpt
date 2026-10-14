import axios from 'axios';

/**
 * Axios instance pre-configured for the backend Auth API.
 *
 * - baseURL '/api' is handled by the Vite dev proxy (→ http://backend:8080)
 *   and by Nginx in production.
 * - withCredentials: true ensures session cookies are sent on every request,
 *   which is required for cookie-based session authentication.
 */
const apiClient = axios.create({
  baseURL: '/api',
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
});

/**
 * Authenticate a user with email and password.
 *
 * @param {string} email    - The user's email address.
 * @param {string} password - The user's plain-text password.
 * @returns {Promise<import('axios').AxiosResponse>}
 */
export function login(email, password) {
  return apiClient.post('/auth/login', { email, password });
}

/**
 * Invalidate the current session on the server side.
 *
 * @returns {Promise<import('axios').AxiosResponse>}
 */
export function logout() {
  return apiClient.post('/auth/logout');
}

/**
 * Retrieve the currently authenticated user's profile.
 * Returns 401 if the session cookie is absent or expired.
 *
 * @returns {Promise<import('axios').AxiosResponse>}
 */
export function getMe() {
  return apiClient.get('/auth/me');
}

export default apiClient;
