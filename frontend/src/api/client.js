import axios from 'axios';

const API_URL = 'https://notes-app-09iq.onrender.com/api/v1';

export const apiClient = axios.create({
    baseURL: API_URL,
    withCredentials: true, // MUST be true to send the HttpOnly refresh token cookie
});

// Attach access token to requests
apiClient.interceptors.request.use((config) => {
    const token = localStorage.getItem('access_token');
    if (token) {
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
});

// Handle 401 errors and auto-refresh the token
apiClient.interceptors.response.use(
    (response) => response,
    async (error) => {
        const originalRequest = error.config;

        if (error.response?.status === 401 && !originalRequest._retry) {
            originalRequest._retry = true;
            try {
                // Attempt to refresh token
                const { data } = await axios.post(`${API_URL}/auth/refresh`, {}, { withCredentials: true });
                localStorage.setItem('access_token', data.access_token);
                
                // Retry original request with new token
                originalRequest.headers.Authorization = `Bearer ${data.access_token}`;
                return apiClient(originalRequest);
            } catch (refreshError) {
                // Refresh failed (cookie expired or revoked)
                localStorage.removeItem('access_token');
                window.location.href = '/login';
                return Promise.reject(refreshError);
            }
        }
        return Promise.reject(error);
    }
);