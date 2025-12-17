import { useEffect, useState } from 'react'
import { fetchPosts, createPost, getImageUrl } from './api'
import PostForm from './components/PostForm'
import './styles.css'

export default function App() {
  const [posts, setPosts] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [search, setSearch] = useState('')

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
    <div className="container">
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
              <img className="post-image" src={getImageUrl(p.image_id)} alt="attachment" />
            )}
          </li>
        ))}
      </ul>
    </div>
  )
}
