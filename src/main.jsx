import React, { useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import {
  Activity, ArrowDownRight, ArrowRight, ArrowUpRight, BadgeCheck, BarChart3,
  BookOpen, Camera, Check, CircleHelp, CloudSun, FileImage, Gauge, Leaf, Menu,
  ScanLine, ShieldCheck, Sprout, Sun, Tractor, TrendingUp, Upload,
  Wheat, X,
} from 'lucide-react'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import './styles.css'

const API = import.meta.env.VITE_API_URL || ''

function IconMark({ small = false }) {
  return <span className={`brand-mark ${small ? 'brand-mark-small' : ''}`}><Leaf size={small ? 18 : 22} strokeWidth={2.1} /></span>
}

function App() {
  const [page, setPage] = useState('Overview')
  const [mobileOpen, setMobileOpen] = useState(false)
  const [health, setHealth] = useState(null)
  const [image, setImage] = useState(null)
  const [imageFile, setImageFile] = useState(null)
  const [diagnosis, setDiagnosis] = useState(null)
  const [diagnoseBusy, setDiagnoseBusy] = useState(false)
  const [plannerOptions, setPlannerOptions] = useState(null)
  const [insights, setInsights] = useState(null)
  const [insightDistrict, setInsightDistrict] = useState('All Gujarat')
  const [form, setForm] = useState({ district: 'Rajkot', crop: 'Groundnut', season: 'Kharif', area_value: 2, area_unit: 'acres', price_value: 5500, price_unit: 'per_quintal', cost_value: 32000, cost_unit: 'per_hectare' })
  const [prediction, setPrediction] = useState(null)
  const [plannerBusy, setPlannerBusy] = useState(false)
  const [error, setError] = useState('')
  const supportedCombinations = plannerOptions?.combinations || []
  const supportedDistricts = new Set(plannerOptions?.supported_districts || [])
  const districtChoices = (plannerOptions?.districts || []).map(value => ({ value, disabled: !supportedDistricts.has(value), label: supportedDistricts.has(value) ? value : `${value} · insufficient history` }))
  const cropChoices = (plannerOptions?.crops || []).map(value => {
    const available = supportedCombinations.some(c => c.district === form.district && c.crop === value)
    return { value, disabled: !available, label: available ? value : `${value} · unavailable for this district` }
  })
  const seasonChoices = (plannerOptions?.seasons || []).map(value => {
    const available = supportedCombinations.some(c => c.district === form.district && c.crop === form.crop && c.season === value)
    return { value, disabled: !available, label: available ? value : `${value} · unavailable for this crop` }
  })

  useEffect(() => {
    fetch(`${API}/api/health`).then(r => r.json()).then(setHealth).catch(() => setHealth({ status: 'offline', models: {} }))
    fetch(`${API}/api/planner/options`).then(r => r.json()).then(setPlannerOptions).catch(() => setPlannerOptions({ data_available: false, districts: [], crops: [], seasons: [], supported_districts: [], combinations: [] }))
    fetch(`${API}/api/insights`).then(r => r.json()).then(setInsights).catch(() => {})
    if ('serviceWorker' in navigator && import.meta.env.PROD) navigator.serviceWorker.register('/sw.js').catch(() => {})
  }, [])
  useEffect(() => {
    if (!plannerOptions?.data_available) return
    setForm(current => {
      const existing = supportedCombinations.some(c => c.district === current.district && c.crop === current.crop && c.season === current.season)
      const selected = existing ? current : supportedCombinations[0]
      return { ...current, district: selected?.district || '', crop: selected?.crop || '', season: selected?.season || '' }
    })
  }, [plannerOptions])

  const modelsReady = health?.status === 'ok' && health?.models?.yield && health?.models?.leaf_disease
  const isReady = health?.status === 'ok'
  const loadInsights = async (district = 'All Gujarat') => {
    setInsightDistrict(district)
    const q = district === 'All Gujarat' ? '' : `?district=${encodeURIComponent(district)}`
    try { setInsights(await fetch(`${API}/api/insights${q}`).then(r => r.json())) } catch { setError('Could not load dataset insights.') }
  }
  const navigate = (target) => { setPage(target); setMobileOpen(false); setError('') }
  const onFile = (file) => {
    if (!file) return
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) { setError('Choose a leaf photo in JPG, PNG, or WEBP format.'); return }
    if (file.size > 8 * 1024 * 1024) { setError('The image must be smaller than 8 MB.'); return }
    setError(''); setDiagnosis(null); setImageFile(file); setImage(URL.createObjectURL(file))
  }
  const useDemoLeaf = async () => {
    try {
      const response = await fetch(`${API}/demo_leaf_spot_pattern.jpg`)
      if (!response.ok) throw new Error('The bundled example image could not be loaded.')
      const blob = await response.blob()
      onFile(new File([blob], 'fasalscope-synthetic-demo-leaf.jpg', { type: 'image/jpeg' }))
    } catch (e) { setError(e.message) }
  }
  const runDiagnosis = async () => {
    if (!imageFile) return
    setDiagnoseBusy(true); setError('')
    const body = new FormData(); body.append('file', imageFile)
    try {
      const res = await fetch(`${API}/api/diagnose`, { method: 'POST', body })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Could not analyze image')
      setDiagnosis(data)
    } catch (e) { setError(e.message) }
    finally { setDiagnoseBusy(false) }
  }
  const runPlanner = async (e) => {
    e.preventDefault(); setPlannerBusy(true); setError(''); setPrediction(null)
    try {
      const res = await fetch(`${API}/api/planner/predict`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ district: form.district, crop: form.crop, season: form.season, area_value: Number(form.area_value), area_unit: form.area_unit, price_value: Number(form.price_value), price_unit: form.price_unit, cost_value: Number(form.cost_value), cost_unit: form.cost_unit }) })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Could not create estimate')
      setPrediction(data)
    } catch (e) { setError(e.message) }
    finally { setPlannerBusy(false) }
  }
  const loadDemoScenario = () => {
    setForm({ ...form, district: 'Rajkot', crop: 'Groundnut', season: 'Kharif', area_value: 2, area_unit: 'acres', price_value: 5500, price_unit: 'per_quintal', cost_value: 32000, cost_unit: 'per_hectare' })
    setPrediction(null); setError('')
  }
  const updatePlannerInput = (key, value) => {
    setForm(current => ({ ...current, [key]: value }))
    setPrediction(null); setError('')
  }
  const money = (n) => new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(n || 0)
  const number = (n) => new Intl.NumberFormat('en-IN', { maximumFractionDigits: 2 }).format(n || 0)

  return <div className="app-shell">
    <aside className={`sidebar ${mobileOpen ? 'sidebar-open' : ''}`}>
      <div className="brand"><IconMark /><span>fasal<span className="brand-light">scope</span></span><button className="mobile-close" onClick={() => setMobileOpen(false)} aria-label="Close menu"><X /></button></div>
      <div className="workspace-label">FIELD WORKSPACE</div>
      <nav className="side-nav">
        <NavItem icon={Gauge} label="Overview" active={page === 'Overview'} onClick={() => navigate('Overview')} />
        <div className="nav-section-label">TOOLS</div>
        <NavItem icon={ScanLine} label="Crop health check" active={page === 'Crop health check'} badge="DL" onClick={() => navigate('Crop health check')} />
        <NavItem icon={Wheat} label="Yield & returns" active={page === 'Yield & returns'} badge="ML" onClick={() => navigate('Yield & returns')} />
        <NavItem icon={BarChart3} label="Data insights" active={page === 'Data insights'} onClick={() => navigate('Data insights')} />
        <div className="nav-section-label">LEARN</div>
        <NavItem icon={BarChart3} label="How predictions work" active={page === 'How predictions work'} onClick={() => navigate('How predictions work')} />
      </nav>
      <div className="sidebar-spacer" />
      <div className="advisor-card"><div className="advisor-icon"><BookOpen size={17} /></div><p>Built to make field data easier to understand.</p><button onClick={() => navigate('How predictions work')}>Explore the guide <ArrowRight size={14} /></button></div>
      <div className="sidebar-profile"><div className="avatar">FS</div><div><strong>Field workspace</strong><small>Gujarat · India</small></div></div>
    </aside>

    {mobileOpen && <button className="scrim" onClick={() => setMobileOpen(false)} aria-label="Close menu" />}
    <main className="main-area">
      <header className="topbar"><button className="menu-button" onClick={() => setMobileOpen(true)} aria-label="Open menu"><Menu /></button><div className="breadcrumb">Workspace <span>/</span> <strong>{page}</strong></div><div className="topbar-right"><span className={`system-state ${modelsReady ? 'state-online' : 'state-wait'}`}><i /> {modelsReady ? 'Models ready' : isReady ? 'Model setup needed' : 'Connecting'}</span><div className="top-avatar" aria-label="FasalScope workspace">FS</div></div></header>
      <div className="page-wrap">
        {page === 'Overview' && <>
          <section className="welcome-row"><div><div className="eyebrow"><Sun size={14} /> YOUR FIELD, IN FOCUS</div><h1>Welcome to FasalScope</h1><p className="page-subtitle">Explore crop health screening, historical yield patterns, and return scenarios.</p></div><div className="today-chip"><span className="weather-symbol"><CloudSun size={19} /></span><span><b>Gujarat, India</b><small>Field insights workspace</small></span></div></section>
          <section className="hero-card"><div className="hero-copy"><div className="hero-tag"><Sprout size={14} /> FIELD INTELLIGENCE, MADE PRACTICAL</div><h2>Make your next<br />field decision with<br /><em>more confidence.</em></h2><p>Screen a leaf photo or explore crop yield and return estimates using historical district data.</p><div className="hero-actions"><button className="button-primary" onClick={() => navigate('Crop health check')}><ScanLine size={16} /> Check crop health <ArrowRight size={16} /></button><button className="button-text-light" onClick={() => navigate('Yield & returns')}>Plan a crop <ArrowRight size={15} /></button></div><div className="hero-footnote"><ShieldCheck size={14} /> Estimates are guidance, not a substitute for local expertise</div></div><div className="hero-art" aria-hidden="true"><div className="sun-disc" /><div className="art-ring ring-one" /><div className="art-ring ring-two" /><div className="hill hill-back" /><div className="hill hill-front" /><div className="plant-stem stem-a"><span /><span /><span /></div><div className="plant-stem stem-b"><span /><span /><span /></div><div className="plant-stem stem-c"><span /><span /><span /></div><div className="art-label label-top"><span className="label-dot" /> DATA-INFORMED</div><div className="art-label label-bottom"><Leaf size={14} /> GROW WITH INSIGHT</div></div></section>
          <section className="section-heading"><div><span className="eyebrow">YOUR TOOLKIT</span><h2>Start with what you need</h2></div><button className="link-button" onClick={() => navigate('How predictions work')}>How it works <ArrowRight size={15} /></button></section>
          <section className="tool-grid"><ToolCard icon={ScanLine} tone="mint" tag="IMAGE SCREENING · DL" title="Check a leaf" text="Upload a clear photo to screen for supported crop health categories." action="Open health check" onClick={() => navigate('Crop health check')} /><ToolCard icon={Wheat} tone="sand" tag="YIELD ESTIMATE · ML" title="Plan a crop" text="Explore historical yield estimates and calculate a return scenario." action="Open farm planner" onClick={() => navigate('Yield & returns')} /></section>
          {insights && <section className="snapshot-strip"><div><span className="eyebrow">DATASET SNAPSHOT</span><h3>Explore the history behind the estimate</h3><p>Historical Gujarat crop records; use the insight page to filter by district.</p></div><div className="snapshot-metric"><b>{insights.summary.records.toLocaleString('en-IN')}</b><small>records</small></div><div className="snapshot-metric"><b>{insights.summary.crops}</b><small>crop types</small></div><div className="snapshot-metric"><b>{insights.summary.first_year}–{insights.summary.last_year}</b><small>recorded years</small></div><button className="snapshot-button" onClick={() => navigate('Data insights')}>Explore data <ArrowRight size={15} /></button></section>}
          <section className="bottom-insight"><div className="insight-icon"><Activity size={18} /></div><div><strong>Two models, two different jobs</strong><p>Image screening uses deep learning. The farm planner uses historical crop records and a regression model.</p></div><button onClick={() => navigate('How predictions work')} aria-label="Learn how predictions work"><ArrowRight size={17} /></button></section>
        </>}

        {page === 'Crop health check' && <>
          <PageTitle eyebrow="IMAGE SCREENING · DEEP LEARNING" title="Crop health check" description="Screen a pepper, potato, or tomato leaf photo. A sample image is included so you can try the flow immediately." />
          <div className="health-layout"><section className="panel upload-panel"><div className="panel-title"><div className="panel-icon mint"><ScanLine size={18} /></div><div><h3>Leaf image</h3><p>Use a clear, well-lit photo of one leaf.</p></div></div>
            <div className="demo-row"><button className="example-link" type="button" onClick={useDemoLeaf}><FileImage size={15} /> Load sample leaf</button><span>Synthetic spot-pattern leaf illustration · output is not test evidence</span></div>
            {!image ? <label className="dropzone" onDragOver={e => e.preventDefault()} onDrop={e => { e.preventDefault(); onFile(e.dataTransfer.files[0]) }}><input type="file" accept="image/png,image/jpeg,image/webp" onChange={e => onFile(e.target.files[0])} /><div className="upload-icon"><Upload size={21} /></div><strong>Drop a leaf photo here</strong><span>or <u>browse files</u></span><small>JPG, PNG or WEBP · up to 8 MB</small><div className="dropzone-hint"><Camera size={15} /> For best results, keep the leaf in focus</div></label> : <div className="image-preview"><img src={image} alt="Selected leaf" /><button className="remove-image" onClick={() => { setImage(null); setImageFile(null); setDiagnosis(null) }}><X size={16} /> Remove photo</button></div>}
            {error && <div className="inline-error"><CircleHelp size={15} /> {error}</div>}
            <button className="button-primary wide" disabled={!imageFile || diagnoseBusy} onClick={runDiagnosis}>{diagnoseBusy ? <><span className="spinner" /> Screening image…</> : <><ScanLine size={16} /> Screen this leaf <ArrowRight size={16} /></>}</button>
          </section><section className="panel result-panel"><div className="panel-title"><div className="panel-icon leaf"><BadgeCheck size={18} /></div><div><h3>Screening result</h3><p>Your result will appear here.</p></div></div>{diagnosis ? <div className="diagnosis-result"><div className="result-status"><span className="status-check"><Check size={18} /></span><div><small>TOP MATCH</small><h4>{diagnosis.predictions[0]?.label?.replaceAll('___', ' · ').replaceAll('_', ' ')}</h4></div><span className="confidence"><small>MODEL SCORE</small>{Math.round((diagnosis.predictions[0]?.confidence || 0) * 100)}%</span></div><p className="result-explain">The image model found this category most similar among the classes it was trained on.</p><div className="top-matches"><span>Other matches</span>{diagnosis.predictions.slice(1).map(p => <div key={p.label}><span>{p.label.replaceAll('___', ' · ').replaceAll('_', ' ')}</span><b>{Math.round(p.confidence * 100)}%</b></div>)}</div><div className="notice-card"><ShieldCheck size={17} /><p>{diagnosis.screening_notice}</p></div><div className="focus-map"><span>MODEL FOCUS MAP · OCCLUSION CHECK</span><img src={diagnosis.focus_map} alt="Occlusion sensitivity overlay showing image regions that changed the model score" /><p>{diagnosis.explanation}</p></div></div> : <div className="empty-result"><div className="empty-illustration"><Leaf size={35} /><span><ScanLine size={16} /></span></div><strong>Ready when you are</strong><p>Choose a leaf photo and run the screening to see the model’s top matches.</p><div className="result-note"><ShieldCheck size={15} /> Screening can help guide a closer look. It cannot confirm a disease.</div></div>}</section></div>
          <div className="info-strip"><div className="info-strip-icon"><ShieldCheck size={18} /></div><p><strong>Use this as an early screening.</strong> The bundled model covers pepper, potato, and tomato labels. Scores are relative model outputs, and photos can vary by lighting, background, and disease stage. Confirm suspected issues with a local agriculture expert before treatment.</p></div>
        </>}

        {page === 'Yield & returns' && <>
          <PageTitle eyebrow="FARM PLANNING · MACHINE LEARNING" title="Explore a crop scenario" description="Select a supported dataset combination, enter your local units, and see how area, price, and cost change the estimate." />
          <div className="planner-layout">
            <section className="panel planner-form-panel">
              <div className="panel-title planner-heading">
                <div className="panel-icon sand"><Tractor size={18} /></div>
                <div><h3>Your field and crop</h3><p>Options are linked to the historical records used by the model.</p></div>
                <button className="example-link planner-example" type="button" disabled={!plannerOptions?.data_available} onClick={loadDemoScenario}><Activity size={14} /> Fill example</button>
              </div>
              {!plannerOptions && <div className="inline-help">Loading supported crop options from the dataset…</div>}
              {plannerOptions && !plannerOptions.data_available && <div className="inline-error"><CircleHelp size={15} /> Crop options could not be loaded. Check that the API is running and the processed dataset is present.</div>}
              <form onSubmit={runPlanner}>
                <div className="form-grid">
                  <FormField label="District" hint="All 27 dataset districts shown; unsupported entries are disabled." value={form.district} onChange={v => {
                    const selected = supportedCombinations.find(c => c.district === v)
                    setForm({ ...form, district: v, crop: selected?.crop || '', season: selected?.season || '' }); setPrediction(null)
                  }} options={districtChoices} />
                  <FormField label="Crop" hint="Unavailable district and crop pairs are disabled." value={form.crop} onChange={v => {
                    const selected = supportedCombinations.find(c => c.district === form.district && c.crop === v)
                    setForm({ ...form, crop: v, season: selected?.season || '' }); setPrediction(null)
                  }} options={cropChoices} />
                  <FormField label="Season" hint="Only model-supported combinations can be selected." value={form.season} onChange={v => { setForm({ ...form, season: v }); setPrediction(null) }} options={seasonChoices} />
                  <label className="field">
                    <span>Farm area</span>
                    <div className="input-with-unit"><input required type="number" min="0.01" step="0.1" value={form.area_value} onChange={e => updatePlannerInput('area_value', e.target.value)} /><select value={form.area_unit} onChange={e => updatePlannerInput('area_unit', e.target.value)}><option value="hectares">hectares</option><option value="acres">acres</option><option value="guntha">guntha</option><option value="square_metres">m²</option></select></div>
                    <small className="field-hint">Converted to hectares before the estimate. 1 acre = 40 guntha.</small>
                  </label>
                  <label className="field">
                    <span>Expected selling price</span>
                    <div className="input-with-unit"><span className="currency-prefix">₹</span><input required type="number" min="0" step="100" value={form.price_value} onChange={e => updatePlannerInput('price_value', e.target.value)} /><select value={form.price_unit} onChange={e => updatePlannerInput('price_unit', e.target.value)}><option value="per_tonne">per tonne</option><option value="per_quintal">per quintal</option><option value="per_kg">per kg</option></select></div>
                    <small className="field-hint">Use a price you choose; example values are not live mandi quotes.</small>
                  </label>
                  <label className="field field-full">
                    <span>Estimated cultivation cost</span>
                    <div className="input-with-unit"><span className="currency-prefix">₹</span><input required type="number" min="0" step="500" value={form.cost_value} onChange={e => updatePlannerInput('cost_value', e.target.value)} /><select value={form.cost_unit} onChange={e => updatePlannerInput('cost_unit', e.target.value)}><option value="per_hectare">per hectare</option><option value="per_acre">per acre</option><option value="per_guntha">per guntha</option><option value="per_square_metre">per m²</option></select></div>
                    <small className="field-hint">Enter your estimate; the app converts it to rupees per hectare.</small>
                  </label>
                </div>
                <div className="form-foot"><span><ShieldCheck size={14} /> Units are converted before calculations</span><button className="button-primary" type="submit" disabled={plannerBusy || !plannerOptions?.data_available}>{plannerBusy ? <><span className="spinner" /> Calculating…</> : <>Estimate scenario <ArrowRight size={16} /></>}</button></div>
              </form>
              {error && <div className="inline-error"><CircleHelp size={15} /> {error}</div>}
            </section>
            <section className={"panel estimate-panel " + (prediction ? "has-estimate" : "")}>
              <div className="estimate-head"><div><span className="eyebrow">SCENARIO ESTIMATE</span><h3>{prediction ? form.crop + ' in ' + form.district : 'Your results will appear here'}</h3></div><div className="estimate-mark"><TrendingUp size={19} /></div></div>
              {prediction ? <>
                <div className="yield-highlight"><span>Estimated yield per hectare</span><strong>{number(prediction.yield_tonnes_per_hectare)} <small>tonnes</small></strong><div><span className="model-pill"><BadgeCheck size={13} /> {prediction.model}</span>{prediction.historical_average != null && <span className="history-hint">Historical average {number(prediction.historical_average)} t/ha</span>}</div></div>
                <div className="converted-summary">Your {number(form.area_value)} {form.area_unit.replace('_', ' ')} was converted to {number(prediction.farm_area_hectares)} hectares · {number(form.price_value)} {form.price_unit.replace('per_', '₹/')} · cost normalized to {money(prediction.cost_per_hectare_inr)}/ha.</div>
                <div className="estimate-rows"><div><span>Estimated total harvest</span><b>{number(prediction.estimated_total_tonnes)} tonnes</b></div><div><span>Estimated gross revenue</span><b>{money(prediction.estimated_revenue_inr)}</b></div><div><span>Estimated cultivation cost</span><b>{money(prediction.estimated_cost_inr)}</b></div></div>
                <div className="net-return"><div><span>Estimated net return</span><strong>{money(prediction.estimated_return_inr)}</strong></div>{prediction.estimated_return_inr >= 0 ? <ArrowUpRight size={21} /> : <ArrowDownRight size={21} />}</div>
                <p className="estimate-disclaimer">{prediction.note}</p>
              </> : <div className="estimate-empty"><div className="estimate-chart"><div className="chart-lines"><i /><i /><i /></div><div className="chart-bars"><b /><b /><b /><b /><b /><b /><b /></div><div className="chart-area" /></div><p>Use the example button or enter your own area, selling price, and cultivation cost.</p><div className="formula-note"><span>Yield model</span><b>District + crop + season → historical yield estimate</b></div><div className="formula-note"><span>Return calculation</span><b>Harvest × price − cultivation cost</b></div></div>}
            </section>
          </div>
          <div className="info-strip"><div className="info-strip-icon"><CircleHelp size={18} /></div><p><strong>How the inputs work.</strong> The model uses the historical district, crop, and season. Area, price, and cost are converted into hectares and rupees per tonne/per hectare; this makes acres, guntha, square metres, quintals, and kilograms usable too. Revenue and return are scenario calculations, not a learned profit prediction.</p></div>
        </>}

        {page === 'Data insights' && <>
          <PageTitle eyebrow="EXPLORE THE TRAINING DATA" title="Gujarat crop insights" description="Review the historical data patterns behind the yield model and compare its held-out evaluation results." />
          <InsightsPanel insights={insights} selectedDistrict={insightDistrict} onDistrictChange={loadInsights} />
          <div className="info-strip"><div className="info-strip-icon"><CircleHelp size={18} /></div><p><strong>Use the chart as context, not a crop ranking.</strong> Historical median yield alone does not account for costs, water, soil, weather, risk, or suitability. The source series ends in 2011–12.</p></div>
        </>}

        {page === 'How predictions work' && <>
          <PageTitle eyebrow="A SIMPLE MODEL GUIDE" title="What happens behind the scenes" description="Two prediction tasks use different data and answer different questions." />
          <div className="guide-grid"><GuideCard number="01" icon={ScanLine} title="Leaf image screening" label="DEEP LEARNING · IMAGE CLASSIFICATION" steps={[['Input','A leaf photo is resized and normalized for the image model.'],['Model','A convolutional neural network compares visual patterns with the disease classes it learned.'],['Result','The app lists the top matches and relative model scores for supported classes.']]} /><GuideCard number="02" icon={Wheat} title="Yield and return planning" label="CLASSICAL ML · REGRESSION" steps={[['Training data','Historical crop records are cleaned and organized by district, crop, season, and year.'],['Model','A regression model estimates yield for the selected combination.'],['Scenario','Estimated harvest is combined with your price and cost inputs to calculate a return scenario.']]} /></div>
          <section className="panel data-panel"><div className="panel-icon mint"><BookOpen size={18} /></div><div><span className="eyebrow">DATA AND LIMITS</span><h3>Predictions need context</h3><p>The image model’s accuracy can drop on photos unlike its training images. Yield predictions reflect historical records, which may not capture changing weather, irrigation, soil health, pest pressure, or local farm practices. Use estimates to explore a scenario, then verify decisions with local agricultural guidance.</p><div className="data-tags"><span>Image classification</span><span>Regression</span><span>Historical data</span><span>Scenario calculation</span></div></div></section>
        </>}
      </div>
      <footer className="footer"><span>© 2026 FasalScope</span><span>Field insights to support better conversations and decisions</span><button onClick={() => navigate('How predictions work')}>Model guide <ArrowRight size={13} /></button></footer>
    </main>
  </div>
}

function NavItem({ icon: Icon, label, active, badge, onClick }) { return <button className={`nav-item ${active ? 'nav-active' : ''}`} onClick={onClick}><Icon size={18} strokeWidth={1.8} /><span>{label}</span>{badge && <small className="nav-badge">{badge}</small>}</button> }
function ToolCard({ icon: Icon, tone, tag, title, text, action, onClick }) { return <button className="tool-card" onClick={onClick}><div className={`tool-icon ${tone}`}><Icon size={20} /></div><span className="tool-tag">{tag}</span><h3>{title}</h3><p>{text}</p><span className="tool-action">{action}<ArrowRight size={15} /></span></button> }
function PageTitle({ eyebrow, title, description }) { return <section className="page-title"><span className="eyebrow">{eyebrow}</span><h1>{title}</h1><p>{description}</p></section> }
function FormField({ label, hint, value, onChange, options = [] }) {
  const normalized = options.map(option => typeof option === 'string' ? { value: option, label: option, disabled: false } : option)
  const available = normalized.filter(option => !option.disabled)
  const selected = available.some(option => option.value === value) ? value : available[0]?.value || ''
  return <label className="field"><span>{label}</span>{hint && <small className="field-hint">{hint}</small>}<select value={selected} disabled={!selected} onChange={e => onChange(e.target.value)}><option value="" disabled>Select {label.toLowerCase()}</option>{normalized.map(o => <option key={o.value} value={o.value} disabled={o.disabled}>{o.label}</option>)}</select></label>
}
function GuideCard({ number, icon: Icon, title, label, steps }) { return <article className="panel guide-card"><div className="guide-top"><span>{number}</span><div className="panel-icon mint"><Icon size={18} /></div></div><span className="eyebrow">{label}</span><h3>{title}</h3><div className="guide-steps">{steps.map(([a,b],i) => <div key={a} className="guide-step"><span>{i+1}</span><p><b>{a}</b>{b}</p></div>)}</div></article> }

function InsightsPanel({ insights, selectedDistrict, onDistrictChange }) {
  if (!insights) return <div className="panel insight-loading"><span className="spinner" /> Loading the crop-history summary…</div>
  const metrics = insights.model_metrics
  return <div className="insights-layout">
    <section className="panel dataset-panel">
      <div className="insight-panel-head"><div><span className="eyebrow">DESCRIPTIVE ANALYSIS</span><h3>{insights.summary.selected_district} · crop patterns</h3></div><label className="district-filter"><span>District</span><select value={selectedDistrict} onChange={e => onDistrictChange(e.target.value)}><option>All Gujarat</option>{insights.district_options.map(d => <option key={d}>{d}</option>)}</select></label></div>
      <div className="insight-kpis"><div><b>{insights.summary.records.toLocaleString('en-IN')}</b><span>historical records</span></div><div><b>{insights.summary.crops}</b><span>crop types</span></div><div><b>{insights.summary.districts}</b><span>districts covered</span></div><div><b>{insights.summary.first_year}–{insights.summary.last_year}</b><span>years in this source</span></div></div>
      <div className="chart-title"><div><h4>Highest historical median yield</h4><p>Top crops in the selected area · tonnes per hectare</p></div><span>Historical only</span></div>
      <div className="yield-chart"><ResponsiveContainer width="100%" height="100%"><BarChart data={insights.crop_medians} layout="vertical" margin={{ top: 5, right: 12, left: 4, bottom: 5 }} barCategoryGap={9}><CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#e8ece4" /><XAxis type="number" tick={{ fill: '#8b958a', fontSize: 9 }} axisLine={false} tickLine={false} /><YAxis type="category" dataKey="crop" width={108} tick={{ fill: '#667368', fontSize: 9 }} axisLine={false} tickLine={false} /><Tooltip cursor={{ fill: '#f4f7f1' }} formatter={(value, name) => [`${Number(value).toFixed(2)} t/ha`, 'Median yield']} contentStyle={{ borderRadius: 7, border: '1px solid #e4e9e0', fontSize: 10 }} /><Bar dataKey="median_yield" fill="#6e965f" radius={[0, 5, 5, 0]} maxBarSize={17} /></BarChart></ResponsiveContainer></div>
      <p className="insight-footnote">{insights.note}</p>
    </section>
    <section className="panel model-metrics-panel"><div className="eyebrow">REGRESSION MODEL CHECK</div><h3>Held-out year evaluation</h3><p className="metrics-caption">Training uses earlier years; evaluation holds out 2009–2011.</p>{metrics ? <><div className="metrics-best"><span>Selected model</span><b>{metrics.best_model}</b></div><div className="metrics-table-wrap"><table className="metrics-table"><thead><tr><th>Model</th><th>MAE ↓</th><th>RMSE ↓</th><th>R² ↑</th></tr></thead><tbody>{metrics.results.map(row => <tr key={row.model} className={row.model === metrics.best_model ? 'metric-selected' : ''}><td>{row.model}</td><td>{row.mae.toFixed(2)}</td><td>{row.rmse.toFixed(2)}</td><td>{row.r2.toFixed(2)}</td></tr>)}</tbody></table></div><div className="metric-note"><CircleHelp size={15} /><p>MAE is average absolute yield error in tonnes/ha. These scores come from old source data and do not establish current-season accuracy.</p></div></> : <p>Evaluation report has not been generated.</p>}</section>
  </div>
}

createRoot(document.getElementById('root')).render(<App />)
