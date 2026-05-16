import { useState, useEffect } from 'react';
import { apiClient } from '../api/client';
import { useAuth } from '../context/AuthContext';
import { useNetwork } from '../hooks/useNetwork';

export default function Dashboard() {
    const { logout } = useAuth();
    const isOnline = useNetwork();
    
    const [notes, setNotes] = useState([]);
    const [sharedNotes, setSharedNotes] = useState([]);
    const [error, setError] = useState('');
    const [newTitle, setNewTitle] = useState('');
    const [newContent, setNewContent] = useState('');
    
    // New state for tab management
    const [activeTab, setActiveTab] = useState('my_notes'); // 'my_notes' | 'shared_notes'

    useEffect(() => {
        fetchNotes();
        fetchSharedNotes();
    }, []);

    const fetchNotes = async () => {
        try {
            const { data } = await apiClient.get('/notes?page=1&size=50');
            setNotes(data.items);
            localStorage.setItem('cached_notes', JSON.stringify(data.items));
            setError('');
        } catch (err) {
            setError(err.response?.data?.message || 'Failed to fetch notes.');
            if (!isOnline) {
                const cached = localStorage.getItem('cached_notes');
                if (cached) setNotes(JSON.parse(cached));
            }
        }
    };

    const fetchSharedNotes = async () => {
        try {
            const { data } = await apiClient.get('/notes/shared?page=1&size=50');
            setSharedNotes(data.items);
        } catch (err) {
            console.error("Failed to fetch shared notes:", err);
        }
    };

    const handleCreateNote = async (e) => {
        e.preventDefault();
        if (!isOnline) return setError("Cannot create notes while offline.");
        try {
            await apiClient.post('/notes', { title: newTitle, content: newContent });
            setNewTitle(''); setNewContent('');
            fetchNotes();
            setActiveTab('my_notes'); // Switch back to my notes to see the new creation
        } catch (err) {
            setError(err.response?.data?.message || 'Failed to create note.');
        }
    };

    const handleDelete = async (id) => {
        if (!isOnline) return setError("Cannot delete while offline.");
        try {
            await apiClient.delete(`/notes/${id}`);
            fetchNotes();
        } catch (err) {
            setError(err.response?.data?.message || 'Failed to delete note.');
        }
    };

    const handleShare = async (id, email) => {
        if (!email) return;
        try {
            await apiClient.post(`/notes/${id}/share`, { share_with_email: email });
            alert("Note shared successfully!");
        } catch (err) {
            setError(err.response?.data?.message || 'Failed to share note.');
        }
    };

    const handleExport = async () => {
        try {
            const response = await apiClient.get('/notes/export', { responseType: 'blob' });
            const url = window.URL.createObjectURL(new Blob([response.data]));
            const link = document.createElement('a');
            link.href = url;
            link.setAttribute('download', 'notes_export.zip');
            document.body.appendChild(link);
            link.click();
            link.remove();
        } catch (err) {
            setError("Export failed.");
        }
    };

    return (
        <main style={{ padding: '2rem 1rem', maxWidth: '1200px', margin: '0 auto' }}>
            <header style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem', gap: '1rem' }}>
                <h1 style={{ fontSize: '1.8rem' }}>Dashboard</h1>
                <button onClick={logout} className="danger" style={{ width: 'auto', padding: '0.5rem 1.5rem' }}>Logout</button>
            </header>

            {!isOnline && (
                <div style={{ background: 'var(--warning-bg)', color: 'var(--warning-text)', padding: '1rem', borderRadius: '6px', marginBottom: '1.5rem' }}>
                    <strong>⚠️ Offline Mode:</strong> Viewing cached notes. Changes cannot be saved until reconnected.
                </div>
            )}
            
            {error && (
                <div style={{ background: 'var(--danger-bg)', color: 'var(--danger-text)', padding: '1rem', borderRadius: '6px', marginBottom: '1.5rem' }}>
                    {error}
                </div>
            )}

            <section style={{ background: 'var(--bg-card)', padding: '1.5rem', borderRadius: '8px', border: '1px solid var(--border-color)', marginBottom: '2rem' }}>
                <h2 style={{ marginBottom: '1rem', fontSize: '1.4rem' }}>Create Note</h2>
                <form onSubmit={handleCreateNote} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                    <input 
                        value={newTitle} 
                        onChange={e => setNewTitle(e.target.value)} 
                        placeholder="Note Title" 
                        required 
                        disabled={!isOnline} 
                    />
                    <textarea 
                        value={newContent} 
                        onChange={e => setNewContent(e.target.value)} 
                        placeholder="Write your note here..." 
                        rows="4" 
                        disabled={!isOnline} 
                        style={{ resize: 'vertical' }}
                    />
                    <button type="submit" disabled={!isOnline} style={{ alignSelf: 'flex-start', padding: '0.75rem 2rem' }}>
                        Save Note
                    </button>
                </form>
            </section>

            {/* --- TAB NAVIGATION --- */}
            <div style={{ display: 'flex', gap: '1rem', marginBottom: '1.5rem', borderBottom: '2px solid var(--border-color)', paddingBottom: '0.5rem' }}>
                <button 
                    onClick={() => setActiveTab('my_notes')}
                    style={{
                        width: 'auto',
                        padding: '0.5rem 1rem',
                        backgroundColor: activeTab === 'my_notes' ? 'var(--primary-brand)' : 'transparent',
                        color: activeTab === 'my_notes' ? 'white' : 'var(--text-primary)',
                        border: activeTab === 'my_notes' ? '1px solid var(--primary-brand)' : '1px solid var(--border-color)',
                    }}
                >
                    My Notes ({notes.length})
                </button>
                <button 
                    onClick={() => setActiveTab('shared_notes')}
                    style={{
                        width: 'auto',
                        padding: '0.5rem 1rem',
                        backgroundColor: activeTab === 'shared_notes' ? 'var(--primary-brand)' : 'transparent',
                        color: activeTab === 'shared_notes' ? 'white' : 'var(--text-primary)',
                        border: activeTab === 'shared_notes' ? '1px solid var(--primary-brand)' : '1px solid var(--border-color)',
                    }}
                >
                    Shared With Me ({sharedNotes.length})
                </button>
            </div>

            {/* --- TAB CONTENT: MY NOTES --- */}
            {activeTab === 'my_notes' && (
                <section>
                    <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'space-between', alignItems: 'center', gap: '1rem' }}>
                        <h2 style={{ fontSize: '1.4rem' }}>My Notes</h2>
                        <button onClick={handleExport} disabled={!isOnline || notes.length === 0} style={{ width: 'auto', padding: '0.5rem 1.5rem' }}>
                            Export as ZIP
                        </button>
                    </div>
                    
                    <div className="notes-grid">
                        {notes.map(note => (
                            <NoteCard key={note.id} note={note} isOnline={isOnline} onDelete={handleDelete} onShare={handleShare} />
                        ))}
                        {notes.length === 0 && <p style={{ color: 'var(--text-secondary)', marginTop: '1rem' }}>No notes found. Create one above!</p>}
                    </div>
                </section>
            )}

            {/* --- TAB CONTENT: SHARED NOTES --- */}
            {activeTab === 'shared_notes' && (
                <section>
                    <h2 style={{ fontSize: '1.4rem', marginBottom: '1rem' }}>Shared With Me</h2>
                    <div className="notes-grid">
                        {sharedNotes.map(note => (
                            <article key={note.id} className="card break-word" style={{ borderStyle: 'dashed', borderColor: 'var(--primary-brand)', backgroundColor: '#f8fafc' }}>
                                <h3 style={{ fontSize: '1.2rem', marginBottom: '0.5rem' }}>{note.title}</h3>
                                <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginBottom: '1rem' }}>
                                    Shared by: <span style={{ fontWeight: 600 }}>{note.shared_by_email}</span>
                                </p>
                                <p style={{ flexGrow: 1, whiteSpace: 'pre-wrap' }}>{note.content}</p>
                                <div style={{ marginTop: '1rem', paddingTop: '1rem', borderTop: '1px solid var(--border-color)', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                                    Permission: {note.permission.toUpperCase()}
                                </div>
                            </article>
                        ))}
                        {sharedNotes.length === 0 && <p style={{ color: 'var(--text-secondary)' }}>No one has shared any notes with you yet.</p>}
                    </div>
                </section>
            )}
        </main>
    );
}

// Sub-component remains the same
function NoteCard({ note, isOnline, onDelete, onShare }) {
    const [shareEmail, setShareEmail] = useState('');

    return (
        <article className="card break-word">
            <h3 style={{ fontSize: '1.2rem', marginBottom: '0.5rem' }}>{note.title}</h3>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginBottom: '1rem' }}>
                Updated: {new Date(note.updated_at).toLocaleString()}
            </p>
            <p style={{ flexGrow: 1, marginBottom: '1.5rem', whiteSpace: 'pre-wrap' }}>
                {note.content}
            </p>
            
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', marginTop: 'auto' }}>
                <div style={{ display: 'flex', gap: '0.5rem' }}>
                    <input 
                        type="email" 
                        placeholder="Friend's Email" 
                        value={shareEmail} 
                        onChange={e => setShareEmail(e.target.value)} 
                        style={{ padding: '0.5rem' }}
                    />
                    <button 
                        onClick={() => { onShare(note.id, shareEmail); setShareEmail(''); }} 
                        disabled={!isOnline}
                        style={{ width: 'auto', padding: '0.5rem 1rem' }}
                    >
                        Share
                    </button>
                </div>
                <button className="danger" onClick={() => onDelete(note.id)} disabled={!isOnline}>
                    Delete
                </button>
            </div>
        </article>
    );
}