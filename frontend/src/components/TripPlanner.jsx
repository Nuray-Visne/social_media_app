import { useState } from 'react'
import { API_URL } from '../api'

export default function TripPlanner() {
  const [city, setCity] = useState('')
  const [concept, setConcept] = useState('')
  const [budget, setBudget] = useState('')
  const [days, setDays] = useState('')
  const [people, setPeople] = useState('')
  const [plan, setPlan] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const submit = async (e) => {
    e.preventDefault()
    console.log('Submitting trip plan', { city, concept, budget, days, people })
    setLoading(true)
    setPlan('')
    setError('')
    try {
      const res = await fetch(`${API_URL}/plan-trip/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          city,
          concept,
          budget,
          days: Number(days),
          people: Number(people)
        }),
      })
      if (!res.ok) throw new Error('Failed to get plan')
      const data = await res.json()
      setPlan(data.plan)
    } catch (err) {
      setError('Failed to get plan')
    } finally {
      setLoading(false)
    }
  }

  return (
    <form onSubmit={submit} className="trip-planner-form">
      <h2>Trip Planner</h2>
      <div className="row">
        <label>City</label>
        <input value={city} onChange={e => setCity(e.target.value)} placeholder="City" required />
      </div>
      <div className="row">
        <label>Concept</label>
        <input value={concept} onChange={e => setConcept(e.target.value)} placeholder="Art, culture, history..." required />
      </div>
      <div className="row">
        <label>Budget (EUR)</label>
        <input type="number" value={budget} onChange={e => setBudget(e.target.value)} placeholder="Budget" required />
      </div>
      <div className="row">
        <label>Days</label>
        <input type="number" value={days} onChange={e => setDays(e.target.value)} placeholder="Number of days" required />
      </div>
      <div className="row">
        <label>People</label>
        <input type="number" value={people} onChange={e => setPeople(e.target.value)} placeholder="Number of people" min="1" required />
      </div>
      <button type="submit" disabled={loading}>{loading ? 'Planning...' : 'Plan Trip'}</button>
      {error && <p className="error">{error}</p>}
      {plan && <pre className="trip-plan">{plan}</pre>}
    </form>
  )
}
