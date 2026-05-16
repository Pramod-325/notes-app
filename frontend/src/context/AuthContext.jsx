import { createContext, useState, useEffect, useContext } from 'react';
import { apiClient } from '../api/client';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
    const [isAuthenticated, setIsAuthenticated] = useState(!!localStorage.getItem('access_token'));
    const [loading, setLoading] = useState(false);

    const login = async (email, password) => {
        const { data } = await apiClient.post('/auth/login', { email, password });
        localStorage.setItem('access_token', data.access_token);
        setIsAuthenticated(true);
    };

    const register = async (email, password, full_name) => {
        await apiClient.post('/auth/register', { email, password, full_name });
    };

    const logout = async () => {
        try {
            await apiClient.post('/auth/logout');
        } catch (err) {
            console.error("Logout API failed, forcing local logout", err);
        } finally {
            localStorage.removeItem('access_token');
            setIsAuthenticated(false);
        }
    };

    return (
        <AuthContext.Provider value={{ isAuthenticated, login, register, logout, loading }}>
            {children}
        </AuthContext.Provider>
    );
};

export const useAuth = () => useContext(AuthContext);