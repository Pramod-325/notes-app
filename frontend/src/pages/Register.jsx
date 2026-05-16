import { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { useNavigate, Link } from 'react-router-dom';

export default function Register() {
    const { register, login } = useAuth();
    const navigate = useNavigate();
    
    const [fullName, setFullName] = useState('');
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError('');
        setLoading(true);
        
        try {
            // 1. Create the account
            await register(email, password, fullName);
            
            // 2. Automatically log the user in so they don't have to type credentials twice
            await login(email, password);
            
            // 3. Redirect to the Dashboard
            navigate('/');
        } catch (err) {
            // Safely capture backend validation errors (like "Email already exists")
            setError(err.response?.data?.message || 'Registration failed. Please try again.');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '1rem' }}>
            <main className="card" style={{ maxWidth: '400px', width: '100%', padding: '2rem' }}>
                <h1 style={{ textAlign: 'center', marginBottom: '1.5rem', fontSize: '1.8rem' }}>Create Account</h1>
                
                {error && (
                    <div style={{ background: 'var(--danger-bg)', color: 'var(--danger-text)', padding: '0.75rem', borderRadius: '6px', marginBottom: '1rem', fontSize: '0.9rem' }}>
                        {error}
                    </div>
                )}

                <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1.2rem' }}>
                    <div>
                        <label htmlFor="fullName" style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 500 }}>Full Name (Optional)</label>
                        <input 
                            id="fullName"
                            type="text" 
                            placeholder="John Doe" 
                            value={fullName} 
                            onChange={e => setFullName(e.target.value)} 
                            disabled={loading}
                        />
                    </div>
                    <div>
                        <label htmlFor="email" style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 500 }}>Email Address</label>
                        <input 
                            id="email"
                            type="email" 
                            placeholder="you@example.com" 
                            value={email} 
                            onChange={e => setEmail(e.target.value)} 
                            required 
                            disabled={loading}
                        />
                    </div>
                    <div>
                        <label htmlFor="password" style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 500 }}>Password</label>
                        <input 
                            id="password"
                            type="password" 
                            placeholder="••••••••" 
                            value={password} 
                            onChange={e => setPassword(e.target.value)} 
                            required 
                            minLength="8"
                            disabled={loading}
                        />
                        <small style={{ color: 'var(--text-secondary)', display: 'block', marginTop: '0.25rem' }}>Must be at least 8 characters.</small>
                    </div>
                    
                    <button type="submit" disabled={loading} style={{ marginTop: '0.5rem', padding: '0.85rem' }}>
                        {loading ? 'Creating account...' : 'Sign Up'}
                    </button>
                </form>
                
                <p style={{ textAlign: 'center', marginTop: '1.5rem', color: 'var(--text-secondary)' }}>
                    Already have an account? <Link to="/login" style={{ color: 'var(--primary-brand)', textDecoration: 'none', fontWeight: 600 }}>Sign in here</Link>
                </p>
            </main>
        </div>
    );
}