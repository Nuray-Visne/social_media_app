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
  const [sentiment, setSentiment] = useState('')
  const [selectedImage, setSelectedImage] = useState(null)

  const load = async (kw = '', sent = '') => {
    setLoading(true)
    setError('')
    try {
      const data = await fetchPosts(kw, sent)
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
      await load(search, sentiment)
    } catch (e) {
      setError('Failed to create post')
    }
  }

  return (
    <div className="container">
      <h1>TravelShare</h1>
      <div className="toolbar">
        <input
          placeholder="Search by username or text..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <select value={sentiment} onChange={e => setSentiment(e.target.value)}>
          <option value="">Sentiment</option>
          <option value="POSITIVE">Positive</option>
          <option value="NEGATIVE">Negative</option>
           {/* Neutral kept for another model */}
           <option value="NEUTRAL">Neutral</option>
        </select>
        <button onClick={() => load(search, sentiment)}>Search</button>
        <button onClick={() => { setSearch(''); setSentiment(''); load('', '') }}>Clear</button>
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
  )
}
