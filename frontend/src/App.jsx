import { useEffect, useState } from 'react'
import { fetchPosts, createPost, getImageUrl, getThumbnailUrl } from './api'
import PostForm from './components/PostForm'
import TripPlanner from './components/TripPlanner'
import './styles.css'

export default function App() {
  const [posts, setPosts] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [search, setSearch] = useState('')
  const [selectedImage, setSelectedImage] = useState(null)

  const load = async (kw = '') => {
    setLoading(true)
    setError('')
    try {
      const data = await fetchPosts(kw)
      setPosts(data.posts || [])
    } catch (e) {
      setError('Failed to load posts')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const onCreate = async (payload) => {
    try {
      await createPost(payload)
      await load(search)
    } catch (e) {
      setError('Failed to create post')
    }
  }

  return (
    <div className="container main-layout">
      <div className="main-content">
        <h1>TravelShare</h1>
        <div className="toolbar">
          <input
            placeholder="Search by username or text..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <button onClick={() => load(search)}>Search</button>
          <button onClick={() => { setSearch(''); load('') }}>Clear</button>
        </div>
        <PostForm onCreate={onCreate} />
        {loading && <p>Loading…</p>}
        {error && <p className="error">{error}</p>}
        <ul className="posts">
          {posts.map((p) => (
            <li key={p.id} className="post">
              <div className="header">
                <strong>@{p.username}</strong>
                <span className="date">{new Date(p.created_at).toLocaleString()}</span>
              </div>
              <p>{p.body}</p>
              {p.image_id && (
                <img 
                  className="post-image" 
                  src={getThumbnailUrl(p.image_id)} 
                  alt="attachment" 
                  onClick={() => setSelectedImage(p.image_id)}
                  style={{ cursor: 'pointer' }}
                  title="Click to view full size"
                />
              )}
            </li>
          ))}
        </ul>
        {/* Full-size image modal */}
        {selectedImage && (
          <div className="modal" onClick={() => setSelectedImage(null)}>
            <div className="modal-content" onClick={(e) => e.stopPropagation()}>
              <button className="close-btn" onClick={() => setSelectedImage(null)}>×</button>
              <img src={getImageUrl(selectedImage)} alt="Full size" />
            </div>
          </div>
        )}
      </div>
      <aside className="sidebar">
        <TripPlanner />
      </aside>
    </div>
  )
}
