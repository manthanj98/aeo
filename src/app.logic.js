// Engine and topic accents, drawn from the brand ramp so charts and legends
// stay on-palette. Engine keys are canonical — see normalizeEngine below.
const ENGINE_COLORS = {
  'ChatGPT': '#C9A961',
  'Perplexity': '#4A2C7A',
  'Google AI Overviews': '#A8893F',
  'Microsoft Co-Pilot': '#D4756B',
  'Claude': '#1A0F2E',
};
const TOPIC_COLORS = {
  'topic_agents': '#C9A961',
  'topic_seo': '#A8893F',
  'topic_data': '#4A2C7A',
  'topic_brand': '#D4756B',
  'topic_pricing': '#2D1B4E',
};

// Series ramp for insight charts, in the order a chart should consume it.
const SERIES = ['#C9A961', '#A8893F', '#D4756B', '#4A2C7A', '#E8D097'];

// Some engine data arrives with shorthand names ("Copilot"). Fold those onto
// the canonical keys so colour lookups and the engine filter never miss a row.
const ENGINE_ALIASES = { 'Copilot': 'Microsoft Co-Pilot', 'Co-Pilot': 'Microsoft Co-Pilot', 'Google AI Overview': 'Google AI Overviews' };
const normalizeEngine = (name) => ENGINE_ALIASES[name] || name;

// Monotonic id source. Date.now() collides when two items are added inside the
// same millisecond, which produces duplicate React keys.
let __seq = 0;
const uid = (prefix) => `${prefix}_${Date.now().toString(36)}${(++__seq).toString(36)}`;

// Trend/percentage helpers — one decimal everywhere so a column never mixes
// "+2 pts" with "+1.3 pts".
const signed1 = (n) => (n >= 0 ? '+' : '') + n.toFixed(1);
const pts = (n) => `${signed1(n)} pts`;

// The zero-state a freshly tracked prompt starts from. Without the full shape,
// the Citation Rate cell and both trend indicators render blank.
const NEW_PROMPT_METRICS = {
  promptType: 'Category Related',
  promptVolume: '—',
  mentionRate: '0.0%',
  mentionTrend: '+0.0 pts',
  citationRate: '0.0%',
  citationTrend: '+0.0 pts',
  positiveRate: '0.0%',
};

class Component extends DCLogic {
  state = {
    activeTab: 'overview',
    promptsSubTab: 'yours',
    searchQuery: '',
    engineFilter: 'all',
    dateFrom: '2026-01-01',
    dateTo: '2026-06-30',
    showDatePicker: false,
    marketingFilter: 'all',
    overviewTimeRange: '180d',
    gscCountryFilter: 'na',
    gscTimeRangeFilter: '180d',
    gscDeviceFilter: 'all',
    citationsCountryFilter: 'na',
    citationsTimeRangeFilter: '180d',
    citationsDeviceFilter: 'all',
    citationsEngineFilter: 'all',
    promptsDateFrom: '2026-06-01',
    promptsDateTo: '2026-06-30',
    promptsRegionFilter: 'na',
    promptsPlatformFilter: 'all',
    keywordsDateFrom: '2026-06-01',
    keywordsDateTo: '2026-06-30',
    keywordsRegionFilter: 'na',
    keywordsPlatformFilter: 'all',
    keywordSearchQuery: '',
    showAddKeywordForm: false,
    keywordInspectId: null,
    promptInspectId: null,
    inspectUrl: null,
    openRowMenuUrl: null,
    selectedMentionKey: null,
    pepperRequested: false,
    insightDetailId: null,
    insightDraftId: null,
    insightPublished: false,
    competitorSearchQuery: '',
    competitorsDateFrom: '2026-06-01',
    competitorsDateTo: '2026-06-30',
    competitorsRegionFilter: 'na',
    competitorsPlatformFilter: 'all',
    showRefreshConfig: false,
    refreshFrequency: 'weekly',
    showAddForm: false,
    showEditTopics: false,
    topicsDraft: [],
    newPromptText: '',
    newPromptTopicId: 'topic_seo',
    newTopicName: '',
    copilotOpen: false,
    copilotInput: '',
    activeInfoKpi: null,
    wizardStep: 1,
    reportTab: 'positions',
    newKeywordText: '',
    newCompetitorText: '',
    brandCompetitors: [
      { id: 'bc_1', domain: 'athenahq.ai' },
      { id: 'bc_2', domain: 'tryprofound.com' },
      { id: 'bc_3', domain: 'peec.ai' },
      { id: 'bc_4', domain: 'conductor.com' },
      { id: 'bc_5', domain: 'semrush.com' },
      { id: 'bc_6', domain: 'brightedge.com' },
      { id: 'bc_7', domain: 'scrunchai.com' },
      { id: 'bc_8', domain: 'airops.com' },
    ],
    brandKeywords: [
      { id: 'kw_1', keyword: 'ai visibility tracking' },
      { id: 'kw_2', keyword: 'best aeo tools 2026' },
      { id: 'kw_3', keyword: 'acme ai visibility' },
      { id: 'kw_4', keyword: 'generative engine optimization' },
      { id: 'kw_5', keyword: 'ai search rank tracker' },
      { id: 'kw_6', keyword: 'chatgpt brand monitoring' },
      { id: 'kw_7', keyword: 'llm citation tracking' },
      { id: 'kw_8', keyword: 'ai overview optimization' },
    ],
    topics: [
      { id: 'topic_agents', name: 'AI Agents & Workflow Automation' },
      { id: 'topic_seo', name: 'Programmatic SEO & Content Scale' },
      { id: 'topic_data', name: 'AI Data Processing & Operations' },
      { id: 'topic_brand', name: 'Brand & Company Info' },
      { id: 'topic_pricing', name: 'Pricing & Competitive Positioning' },
    ],
    trackedPrompts: [
      { prompt_id: 'pt_1', topicId: 'topic_agents', prompt_text: 'How do I build custom AI agents?', promptType: 'Category Related', promptVolume: '2,400', mentionRate: '38.0%', mentionTrend: '-3.9 pts', citationRate: '20.9%', citationTrend: '-2.2 pts', positiveRate: '72.0%' },
      { prompt_id: 'pt_2', topicId: 'topic_agents', prompt_text: 'Can AI workflows automate customer support tasks?', promptType: 'Category Related', promptVolume: '1,800', mentionRate: '41.0%', mentionTrend: '-2.6 pts', citationRate: '24.6%', citationTrend: '-1.1 pts', positiveRate: '68.0%' },
      { prompt_id: 'pt_3', topicId: 'topic_agents', prompt_text: 'How to integrate LLMs into business workflows?', promptType: 'Category Related', promptVolume: '3,100', mentionRate: '29.0%', mentionTrend: '-1.3 pts', citationRate: '18.9%', citationTrend: '+0.0 pts', positiveRate: '61.0%' },
      { prompt_id: 'pt_4', topicId: 'topic_agents', prompt_text: 'What are the best workflow automation practices?', promptType: 'Category Related', promptVolume: '2,900', mentionRate: '33.0%', mentionTrend: '+0.0 pts', citationRate: '23.1%', citationTrend: '+1.1 pts', positiveRate: '75.0%' },
      { prompt_id: 'pt_5', topicId: 'topic_brand', prompt_text: 'What is Acme and how does it work?', promptType: 'Brand Related', promptVolume: '880', mentionRate: '91.0%', mentionTrend: '+1.3 pts', citationRate: '68.3%', citationTrend: '+2.2 pts', positiveRate: '94.0%' },
      { prompt_id: 'pt_6', topicId: 'topic_agents', prompt_text: 'Top tools for building multi-agent AI workflows?', promptType: 'Category Related', promptVolume: '2,200', mentionRate: '46.0%', mentionTrend: '+2.6 pts', citationRate: '25.3%', citationTrend: '-2.2 pts', positiveRate: '70.0%' },
      { prompt_id: 'pt_7', topicId: 'topic_agents', prompt_text: 'Which AI workflow builder has best integrations?', promptType: 'Category Related', promptVolume: '1,500', mentionRate: '52.0%', mentionTrend: '+3.9 pts', citationRate: '31.2%', citationTrend: '-1.1 pts', positiveRate: '64.0%' },
      { prompt_id: 'pt_8', topicId: 'topic_agents', prompt_text: 'Compare leading enterprise AI automation platforms.', promptType: 'Category Related', promptVolume: '2,700', mentionRate: '44.0%', mentionTrend: '-3.9 pts', citationRate: '28.6%', citationTrend: '+0.0 pts', positiveRate: '58.0%' },
      { prompt_id: 'pt_9', topicId: 'topic_pricing', prompt_text: 'Is Acme worth it for content scaling?', promptType: 'Brand Related', promptVolume: '640', mentionRate: '88.0%', mentionTrend: '-2.6 pts', citationRate: '61.6%', citationTrend: '+1.1 pts', positiveRate: '91.0%' },
      { prompt_id: 'pt_10', topicId: 'topic_seo', prompt_text: 'Can AI tools automate programmatic SEO campaigns?', promptType: 'Category Related', promptVolume: '1,900', mentionRate: '36.0%', mentionTrend: '-1.3 pts', citationRate: '27%', citationTrend: '+2.2 pts', positiveRate: '66.0%' },
      { prompt_id: 'pt_11', topicId: 'topic_seo', prompt_text: 'How to create SEO optimized blog posts?', promptType: 'Category Related', promptVolume: '4,300', mentionRate: '24.0%', mentionTrend: '+0.0 pts', citationRate: '13.2%', citationTrend: '-2.2 pts', positiveRate: '63.0%' },
      { prompt_id: 'pt_12', topicId: 'topic_seo', prompt_text: 'How to build an AI SEO strategy?', promptType: 'Category Related', promptVolume: '2,600', mentionRate: '31.0%', mentionTrend: '+1.3 pts', citationRate: '18.6%', citationTrend: '-1.1 pts', positiveRate: '69.0%' },
      { prompt_id: 'pt_13', topicId: 'topic_pricing', prompt_text: 'How does Acme pricing compare to competitors?', promptType: 'Brand Related', promptVolume: '720', mentionRate: '100.0%', mentionTrend: '+2.6 pts', citationRate: '65%', citationTrend: '+0.0 pts', positiveRate: '100.0%' },
      { prompt_id: 'pt_14', topicId: 'topic_seo', prompt_text: 'Top platforms for AI-driven content scaling.', promptType: 'Category Related', promptVolume: '1,700', mentionRate: '55.0%', mentionTrend: '+3.9 pts', citationRate: '38.5%', citationTrend: '+1.1 pts', positiveRate: '100.0%' },
      { prompt_id: 'pt_15', topicId: 'topic_data', prompt_text: 'How to extract structured data using LLMs?', promptType: 'Category Related', promptVolume: '1,300', mentionRate: '27.0%', mentionTrend: '-3.9 pts', citationRate: '20.3%', citationTrend: '+2.2 pts', positiveRate: '57.0%' },
      { prompt_id: 'pt_16', topicId: 'topic_data', prompt_text: 'Can AI automate bulk data classification?', promptType: 'Category Related', promptVolume: '1,100', mentionRate: '34.0%', mentionTrend: '-2.6 pts', citationRate: '18.7%', citationTrend: '-2.2 pts', positiveRate: '62.0%' },
      { prompt_id: 'pt_17', topicId: 'topic_data', prompt_text: 'How to clean unstructured data with AI?', promptType: 'Category Related', promptVolume: '950', mentionRate: '22.0%', mentionTrend: '-1.3 pts', citationRate: '13.2%', citationTrend: '-1.1 pts', positiveRate: '55.0%' },
      { prompt_id: 'pt_18', topicId: 'topic_data', prompt_text: 'What is the best way to process data?', promptType: 'Category Related', promptVolume: '3,600', mentionRate: '19.0%', mentionTrend: '+0.0 pts', citationRate: '12.4%', citationTrend: '+0.0 pts', positiveRate: '60.0%' },
      { prompt_id: 'pt_19', topicId: 'topic_data', prompt_text: 'Best AI tools for bulk data processing.', promptType: 'Category Related', promptVolume: '2,000', mentionRate: '40.0%', mentionTrend: '+1.3 pts', citationRate: '28%', citationTrend: '+1.1 pts', positiveRate: '73.0%' },
      { prompt_id: 'pt_20', topicId: 'topic_data', prompt_text: 'Top-rated LLM data extraction platforms.', promptType: 'Category Related', promptVolume: '1,400', mentionRate: '37.0%', mentionTrend: '+2.6 pts', citationRate: '27.8%', citationTrend: '+2.2 pts', positiveRate: '65.0%' },
    ],
    recommendedFromPlatform: [
      { id: 'rp_1', topicId: 'topic_data', text: 'which AI data tool is most secure' },
      { id: 'rp_2', topicId: 'topic_data', text: 'compare leading AI data scraping solutions' },
      { id: 'rp_3', topicId: 'topic_seo', text: 'best enterprise platforms for AI content operations' },
    ],
    recommendedKeywords: [
      { id: 'rk_1', text: 'ai citation benchmarks' },
      { id: 'rk_2', text: 'llm brand visibility tools' },
      { id: 'rk_3', text: 'aeo audit checklist' },
    ],
    recommendedCompetitors: [
      { id: 'rc_1', domain: 'writesonic.com' },
      { id: 'rc_2', domain: 'surferseo.com' },
    ],
    recommendedGuidelines: [
      { id: 'rg_1', text: "Always spell out acronyms (AEO, GEO) on first use per document" },
      { id: 'rg_2', text: 'Round percentages to one decimal place in customer-facing reports' },
    ],
    brandGuidanceNotes: [],
    newGuidanceText: '',
    copilotSuggestions: [
      { id: 'cs_1', topicId: 'topic_data', text: 'best enterprise platforms for AI data operations' },
      { id: 'cs_2', topicId: 'topic_agents', text: 'top AI agent platforms for enterprises' },
      { id: 'cs_3', topicId: 'topic_seo', text: 'what is the best way to process content at scale' },
    ],
  };

  allPrompts = [
    { prompt_text: 'best AEO and GEO visibility tracking tools', ai_engine: 'ChatGPT', mentioned: true, position: 2, sentiment: 'Positive', date: '2026-06-24', response_excerpt: 'Acme offers a toolkit that tracks brand visibility across major AI engines...', citation_urls: ['a','b'], competitor_brands: ['AthenaHQ', 'Profound'] },
    { prompt_text: 'how to monitor brand mentions in ChatGPT answers', ai_engine: 'Perplexity', mentioned: true, position: 1, sentiment: 'Positive', date: '2026-06-21', response_excerpt: 'Tools like Acme and Profound let you track how often your brand appears...', citation_urls: ['a'], competitor_brands: ['Profound'] },
    { prompt_text: 'alternatives to traditional SEO software', ai_engine: 'Google AI Overviews', mentioned: false, position: null, sentiment: 'Neutral', date: '2026-06-18', response_excerpt: 'Common tools mentioned include Conductor, Brightedge, and Semrush for keyword and backlink analysis...', citation_urls: [], competitor_brands: ['Conductor', 'Brightedge', 'Semrush'] },
    { prompt_text: 'is Acme good for enterprise AEO', ai_engine: 'ChatGPT', mentioned: true, position: 1, sentiment: 'Positive', date: '2026-06-15', response_excerpt: 'Acme is widely used by enterprise teams for keyword research, site audits, and now AI visibility tracking...', citation_urls: ['a','b','c'], competitor_brands: [] },
    { prompt_text: 'best rank tracking software comparison', ai_engine: 'Microsoft Co-Pilot', mentioned: true, position: 3, sentiment: 'Neutral', date: '2026-06-11', response_excerpt: 'Popular options include Acme, Scrunch AI, and airOps, each with different strengths in reporting...', citation_urls: ['a'], competitor_brands: ['Scrunch AI', 'airOps'] },
    { prompt_text: 'how does Claude decide which brands to cite', ai_engine: 'Claude', mentioned: true, position: 2, sentiment: 'Positive', date: '2026-06-08', response_excerpt: 'Claude tends to cite Acme and AthenaHQ when asked about AEO tracking platforms...', citation_urls: ['a', 'b'], competitor_brands: ['AthenaHQ'] },
  ];

  citationsData = [
    { url: 'www.acme.com/blog-post/athena-vs-semrush', topPrompt: 'best AEO and GEO visibility tracking tools', citations_count: 142, avg_citation_position: 1.8, change_vs_previous: '+18%', avgPosDelta: '+14%', engines: ['ChatGPT', 'Perplexity', 'Microsoft Co-Pilot'] },
    { url: 'www.acme.com/case-study/acceldata', topPrompt: 'how does acceldata improve ai search rankings', citations_count: 96, avg_citation_position: 2.3, engines: ['ChatGPT', 'Google AI Overviews'] },
    { url: 'www.acme.com/features/atlas', topPrompt: 'brand visibility monitoring tools', citations_count: 74, avg_citation_position: 3.1, change_vs_previous: '-16%', engines: ['Perplexity'] },
    { url: 'www.acme.com/report/state-of-aeo-2026', topPrompt: 'state of AEO and GEO industry trends 2026', citations_count: 51, avg_citation_position: 2.7, engines: ['ChatGPT', 'Microsoft Co-Pilot'] },
    { url: 'www.acme.com/guide/geo-vs-seo-explained', topPrompt: 'difference between geo and seo strategy', citations_count: 44, avg_citation_position: 3.4, change_vs_previous: '+17%', engines: ['ChatGPT', 'Claude'] },
    { url: 'www.acme.com/blog-post/how-ai-overviews-work', topPrompt: 'how does google ai overview pick sources', citations_count: 39, avg_citation_position: 2.9, engines: ['Google AI Overviews'] },
    { url: 'www.acme.com/case-study/northwind-retail', topPrompt: 'ecommerce brand visibility case study', citations_count: 33, avg_citation_position: 4.1, change_vs_previous: '+19%', engines: ['Perplexity', 'ChatGPT'] },
    { url: 'www.acme.com/features/prompt-tracking', topPrompt: 'track brand mentions across ai prompts', citations_count: 28, avg_citation_position: 3.6, engines: ['Claude', 'Microsoft Co-Pilot'] },
    { url: 'www.acme.com/blog-post/citation-rate-benchmarks', topPrompt: 'average citation rate by industry', citations_count: 21, avg_citation_position: 4.8, change_vs_previous: '-15%', engines: ['ChatGPT'] },
    { url: 'www.acme.com/report/competitor-share-of-voice', topPrompt: 'share of voice vs competitors in ai search', citations_count: 17, avg_citation_position: 5.2, engines: ['Perplexity', 'Google AI Overviews'] },
  ];

  seoCompetitors = [
    { domain: 'athenahq.ai', as: 58 },
    { domain: 'tryprofound.com', as: 44 },
    { domain: 'peec.ai', as: 39 },
  ];
  movers = [
    { kw: 'how to optimize for ai search', vol: '4,100', up: true, down: false, change: 6 },
    { kw: 'seo vs geo strategy', vol: '2,200', up: false, down: true, change: 5 },
    { kw: 'generative engine optimization', vol: '3,300', up: true, down: false, change: 4 },
    { kw: 'ai overview optimization', vol: '1,300', up: true, down: false, change: 3 },
    { kw: 'ai search rank tracker', vol: '2,900', up: false, down: true, change: 3 },
  ];
  seoKeywords = [
    { kw: 'ai visibility tracking', url: '/features/ai-visibility', pos: 3, up: true, down: false, flat: false, change: 2, vol: '8,100', value: '$612', kd: 42, features: ['AI Overview', 'Sitelinks'] },
    { kw: 'best aeo tools 2026', url: '/blog/best-aeo-tools', pos: 7, up: false, down: true, flat: false, change: 1, vol: '5,400', value: '$284', kd: 55, features: ['AI Overview'] },
    { kw: 'acme ai visibility', url: '/', pos: 1, up: false, down: false, flat: true, change: 0, vol: '720', value: '$98', kd: 12, features: ['Sitelinks'] },
    { kw: 'generative engine optimization', url: '/guide/geo-explained', pos: 5, up: true, down: false, flat: false, change: 4, vol: '3,300', value: '$221', kd: 38, features: ['Sitelinks'] },
    { kw: 'ai search rank tracker', url: '/features/rank-tracker', pos: 12, up: false, down: true, flat: false, change: 3, vol: '2,900', value: '$76', kd: 29, features: [] },
    { kw: 'chatgpt brand monitoring', url: '/features/chatgpt-monitoring', pos: 4, up: true, down: false, flat: false, change: 1, vol: '1,900', value: '$134', kd: 33, features: ['AI Overview'] },
    { kw: 'how to optimize for ai search', url: '/blog/optimize-for-ai-search', pos: 9, up: true, down: false, flat: false, change: 6, vol: '4,100', value: '$67', kd: 24, features: ['Video', 'AI Overview'] },
    { kw: 'llm citation tracking', url: '/features/citation-tracking', pos: 6, up: false, down: true, flat: false, change: 2, vol: '1,600', value: '$92', kd: 31, features: [] },
    { kw: 'seo vs geo strategy', url: '/guide/seo-vs-geo', pos: 15, up: false, down: true, flat: false, change: 5, vol: '2,200', value: '$58', kd: 47, features: ['Sitelinks'] },
    { kw: 'ai overview optimization', url: '/guide/ai-overviews', pos: 8, up: true, down: false, flat: false, change: 3, vol: '1,300', value: '$41', kd: 26, features: [] },
  ];
  backlinkDomains = [
    { domain: 'searchengineland.com', as: 71, count: 84, type: 'Dofollow', seen: 'Jan 2024' },
    { domain: 'reddit.com/r/SEO', as: 94, count: 41, type: 'Mixed', seen: 'Mar 2025' },
    { domain: 'moz.com/blog', as: 68, count: 29, type: 'Dofollow', seen: 'Nov 2024' },
    { domain: 'g2.com', as: 91, count: 22, type: 'Nofollow', seen: 'Feb 2025' },
    { domain: 'seoforums.net', as: 38, count: 156, type: 'Dofollow', seen: 'Aug 2023' },
  ];
  trackedKeywords = [
    { kw: 'ai visibility tracking', pos: 3, up: true, down: false, flat: false, change: 2, vol: '8,100', kd: 42, features: ['AI Overview'] },
    { kw: 'best aeo tools 2026', pos: 7, up: false, down: true, flat: false, change: 1, vol: '5,400', kd: 55, features: ['AI Overview'] },
    { kw: 'generative engine optimization', pos: 5, up: true, down: false, flat: false, change: 4, vol: '3,300', kd: 38, features: [] },
    { kw: 'chatgpt brand monitoring', pos: 4, up: true, down: false, flat: false, change: 1, vol: '1,900', kd: 33, features: ['AI Overview'] },
    { kw: 'llm citation tracking', pos: 6, up: false, down: true, flat: false, change: 2, vol: '1,600', kd: 31, features: [] },
    { kw: 'ai overview optimization', pos: 8, up: true, down: false, flat: false, change: 3, vol: '1,300', kd: 26, features: [] },
  ];
  landingPages = [
    { url: '/features/ai-visibility', count: 14, traffic: '4,120' },
    { url: '/blog/best-aeo-tools', count: 9, traffic: '2,860' },
    { url: '/guide/geo-explained', count: 6, traffic: '1,410' },
    { url: '/', count: 3, traffic: '980' },
  ];
  competitorPages = [
    { domain: 'athenahq.ai', url: '/product/ai-visibility', kw: 'ai visibility tracking', pos: 1 },
    { domain: 'tryprofound.com', url: '/reviews/aeo-platforms', kw: 'best aeo tools 2026', pos: 4 },
    { domain: 'athenahq.ai', url: '/guide/geo-basics', kw: 'generative engine optimization', pos: 2 },
    { domain: 'peec.ai', url: '/features/rank-tracker', kw: 'ai search rank tracker', pos: 9 },
  ];
  discovered = [
    { domain: 'writesonic.com', shared: 18, avgPos: 11.2 },
    { domain: 'surferseo.com', shared: 14, avgPos: 14.8 },
    { domain: 'clearscope.io', shared: 9, avgPos: 22.4 },
    { domain: 'marketmuse.com', shared: 7, avgPos: 26.1 },
  ];
  compRows = [
    { domain: 'Acme (you)', as: 47, traffic: '24.6K', keywords: '3,842', backlinks: '12,842' },
    { domain: 'AthenaHQ', as: 58, traffic: '41.2K', keywords: '5,910', backlinks: '28,400' },
    { domain: 'Profound', as: 44, traffic: '19.8K', keywords: '3,120', backlinks: '9,650' },
    { domain: 'Peec AI', as: 39, traffic: '12.4K', keywords: '2,240', backlinks: '6,180' },
  ];
  sharedKeywords = [
    { kw: 'ai visibility tracking', you: 3, summit: 1, basecamp: 8, ridgeline: 14 },
    { kw: 'generative engine optimization', you: 5, summit: 2, basecamp: 6, ridgeline: 22 },
    { kw: 'best aeo tools 2026', you: 7, summit: 3, basecamp: 4, ridgeline: 19 },
    { kw: 'ai search rank tracker', you: 12, summit: 9, basecamp: 5, ridgeline: 31 },
  ];
  gscQueries = [
    { query: 'search console api', impressions: '142,600', clicks: '8,412', ctr: '5.9%', position: '4.2' },
    { query: 'gsc search analytics query', impressions: '98,700', clicks: '6,120', ctr: '6.2%', position: '3.8' },
    { query: 'url inspection api', impressions: '211,300', clicks: '5,890', ctr: '2.8%', position: '9.1' },
    { query: 'site:acme.com', impressions: '61,000', clicks: '4,510', ctr: '7.4%', position: '2.1' },
    { query: 'sitemap indexed vs submitted', impressions: '89,400', clicks: '3,220', ctr: '3.6%', position: '11.4' },
    { query: 'mobile friendly test deprecated', impressions: '54,900', clicks: '2,140', ctr: '3.9%', position: '15.2' },
    { query: 'search console python', impressions: '42,100', clicks: '1,980', ctr: '4.7%', position: '8.6' },
  ];
  gscPages = [
    { path: '/blog/search-console-api-guide', clicks: '12,400', ctr: '5.9%', position: '4.1' },
    { path: '/docs/url-inspection', clicks: '9,800', ctr: '5.2%', position: '5.3' },
    { path: '/blog/sitemap-best-practices', clicks: '7,200', ctr: '5.1%', position: '6.8' },
    { path: '/docs/searchanalytics-query', clicks: '6,500', ctr: '5.4%', position: '4.9' },
    { path: '/blog/mobile-usability-2026', clicks: '4,100', ctr: '4.3%', position: '9.2' },
    { path: '/pricing', clicks: '3,900', ctr: '1.9%', position: '18.4' },
  ];
  inspections = [
    { path: '/blog/search-console-api-guide', when: 'Just now', verdict: 'PASS', badgeBg: 'var(--teal-soft)', badgeColor: 'var(--pos)' },
    { path: '/docs/url-inspection', when: '1 hour ago', verdict: 'PASS', badgeBg: 'var(--teal-soft)', badgeColor: 'var(--pos)' },
    { path: '/pricing', when: 'Yesterday', verdict: 'PARTIAL', badgeBg: 'var(--warn-bg)', badgeColor: 'var(--warn)' },
    { path: '/blog/mobile-usability-2026', when: '2 days ago', verdict: 'FAIL', badgeBg: 'var(--neg-bg)', badgeColor: 'var(--neg)' },
  ];
  sitemaps = [
    { path: 'sitemap.xml', status: 'Processed', statusBg: 'var(--teal-soft)', statusColor: 'var(--pos)', submitted: '1,240', indexed: '1,198', pct: '97%', barColor: 'var(--teal-deep)', lastDownloaded: '2 hours ago', warnings: '—' },
    { path: 'blog-sitemap.xml', status: 'Processed', statusBg: 'var(--teal-soft)', statusColor: 'var(--pos)', submitted: '412', indexed: '349', pct: '85%', barColor: 'var(--teal-deep)', lastDownloaded: '6 hours ago', warnings: '3' },
    { path: 'docs-sitemap.xml', status: 'Pending', statusBg: 'var(--warn-bg)', statusColor: 'var(--warn)', submitted: '88', indexed: '0', pct: '0%', barColor: 'var(--teal-deep)', lastDownloaded: '—', warnings: '—' },
    { path: 'news-sitemap.xml', status: 'Processed', statusBg: 'var(--teal-soft)', statusColor: 'var(--pos)', submitted: '56', indexed: '21', pct: '38%', barColor: 'var(--amber)', lastDownloaded: '1 day ago', warnings: '2 errors' },
  ];

  setTab(tab) { this.setState({ activeTab: tab }); }
  topicName(topics, id) { const t = topics.find(x => x.id === id); return t ? t.name : 'Uncategorized'; }

  // Search-volume band. A freshly tracked prompt has no volume yet, so anything
  // non-numeric reports as an em dash rather than falling through to "Very Low".
  volumeLabel(volume) {
    const raw = String(volume ?? '').replace(/,/g, '').trim();
    if (!/^\d+$/.test(raw)) return '—';
    const n = parseInt(raw, 10);
    if (n >= 3000) return 'Very High';
    if (n >= 2000) return 'High';
    if (n >= 1200) return 'Medium';
    if (n >= 500) return 'Low';
    return 'Very Low';
  }

  trendColor(trend) { return String(trend ?? '').trim().startsWith('-') ? 'var(--neg)' : 'var(--pos)'; }

  // Share of voice tracks mention rate. Floored at 0 — a prompt with no
  // mentions must not report a fabricated 1%.
  shareOfVoice(mentionRate) {
    const mention = parseFloat(mentionRate) || 0;
    return Math.max(0, Math.round(mention * 0.34)) + '%';
  }
  sparkPoints(seed, w, h) {
    let x = 0;
    for (let i = 0; i < seed.length; i++) x = (x * 31 + seed.charCodeAt(i)) >>> 0;
    const vals = [];
    let v = 0.5;
    for (let i = 0; i < 8; i++) {
      x = (x * 1103515245 + 12345) >>> 0;
      v = Math.max(0.1, Math.min(0.9, v + ((x % 100) / 100 - 0.5) * 0.5));
      vals.push(v);
    }
    return vals.map((val, i) => `${(i / (vals.length - 1)) * w},${h - val * h}`).join(' ');
  }

  renderVals() {
    const s = this.state;

    const tabDefs = [
      { key: 'overview', label: 'Performance' },
      { key: 'insights', label: 'Insights' },
    ];
    const insightsRaw = [
      {
        id: 'ins_1', articleAction: 'update', severity: 'Medium', severityBg: 'var(--warn-bg)', severityColor: 'var(--warn)', timeAgo: '12h',
        title: 'Citation Rate declined for /blog-post/how-ai-overviews-work over the past 3 weeks',
        statValue: '39%', statDelta: '\u25bc 11% across 39 citations', statDeltaColor: 'var(--neg)',
        chartType: 'line', chartLine1: '0,54 40,50 80,46 120,48', chartLine2: '120,48 160,58 200,68 240,74 280,78', chartColor: 'var(--amber)',
        rootCauseTag: 'Google AI Overviews \u00b7 71% of citations', rootCauseText: 'Citation share dropped after a Google AI Overviews ranking update deprioritized this URL in favor of fresher competitor content.',
        impactTag: 'Impact: Medium', impactText: 'Losing citation share on a top-performing page compounds — the longer this goes unaddressed, the harder it is to reclaim position from AthenaHQ. Protects existing AI-driven traffic and keeps this page contributing to overall Visibility Score.',
        contributors: [{ label: 'Engine', value: 'Google AI Overviews', pct: '71%', sub: '28 citations' }, { label: 'Region', value: 'United States', pct: '64%', sub: '25 citations' }],
      },
      {
        id: 'ins_2', articleAction: 'draft', severity: 'High', severityBg: 'var(--neg-bg)', severityColor: 'var(--neg)', timeAgo: '1d',
        title: 'Pricing-related prompts have zero brand citations this month',
        statValue: '0', statDelta: '\u25bc no citations across 6 pricing prompts', statDeltaColor: 'var(--neg)',
        chartType: 'bar', barItems: [{ label: 'Acme', value: '0', h: '4%', color: 'var(--muted)' }, { label: 'AthenaHQ', value: '4', h: '80%', color: 'var(--amber)' }, { label: 'Profound', value: '3', h: '60%', color: 'var(--amber)' }, { label: 'Peec AI', value: '1', h: '20%', color: 'var(--amber-light)' }],
        rootCauseTag: 'Competitor cited instead \u00b7 4 of 6 prompts', rootCauseText: 'AthenaHQ and Profound are being cited for pricing-comparison prompts where Acme has no dedicated pricing page content.',
        impactTag: 'Impact: High', impactText: 'Zero citations on high-intent pricing prompts means prospects comparing options never see Acme mentioned at the moment they\'re closest to a decision. Closing this gap directly supports pipeline — pricing prompts sit late in the buyer journey.',
        contributors: [{ label: 'Prompt type', value: 'Brand Related', pct: '100%', sub: '6 prompts' }, { label: 'Engine', value: 'ChatGPT', pct: '50%', sub: '3 prompts' }],
      },
      {
        id: 'ins_3', articleAction: 'update', severity: 'Low', severityBg: 'var(--teal-soft)', severityColor: 'var(--pos)', timeAgo: '2d',
        title: 'Traffic protection opportunity: /report/state-of-aeo-2026 is gaining both clicks and citations',
        statValue: '51', statDelta: '\u25b2 11% citations, +19% impressions', statDeltaColor: 'var(--pos)',
        chartType: 'line', chartLine1: '0,80 40,74 80,68 120,60', chartLine2: '120,60 160,50 200,42 240,34 280,28', chartColor: 'var(--teal-deep)',
        rootCauseTag: 'AI Overviews + Copilot \u00b7 rising together', rootCauseText: 'Both AI citation volume and organic search impressions are trending up together — a strong candidate to double down on with fresh content.',
        impactTag: 'Impact: Low', impactText: 'This page is already compounding gains on its own; the main risk is under-investing while it\'s working. Doubling down here is the cheapest way to grow Citation Rate and Visibility Score this quarter.',
        contributors: [{ label: 'Engine', value: 'ChatGPT', pct: '46%', sub: '23 citations' }, { label: 'Region', value: 'United States', pct: '58%', sub: '30 citations' }],
      },
      {
        id: 'ins_4', articleAction: 'update', severity: 'Medium', severityBg: 'var(--warn-bg)', severityColor: 'var(--warn)', timeAgo: '3d',
        title: 'Quick win: /blog-post/citation-rate-benchmarks has high impressions but low CTR, despite a strong citation rate',
        statValue: '4.6%', statDelta: 'CTR vs 22,300 impressions \u00b7 citation rate 21%', statDeltaColor: 'var(--warn)',
        chartType: 'hbar', hbarItems: [{ label: 'CTR', value: '4.6%', pct: '23%', color: 'var(--teal-deep)' }, { label: 'Citation rate', value: '21%', pct: '84%', color: 'var(--teal-deep)' }],
        rootCauseTag: 'High impressions + low CTR + high citation rate', rootCauseText: 'This page already shows strong AI citation performance — optimizing the title tag and meta description for traditional SEO could lift CTR without risking AI presence.',
        impactTag: 'Impact: Medium', impactText: 'High impressions with low CTR means real search demand is landing on this page but bouncing before conversion. A CTR lift here flows straight into organic traffic without any additional AI-visibility investment.',
        contributors: [{ label: 'Impressions', value: '22,300', pct: 'High', sub: 'via Search Console' }, { label: 'Citation rate', value: '21%', pct: 'Strong', sub: 'via AI engines' }],
      },
      {
        id: 'ins_5', articleAction: 'update', severity: 'Medium', severityBg: 'var(--warn-bg)', severityColor: 'var(--warn)', timeAgo: '4d',
        title: 'AI opportunity: /report/competitor-share-of-voice has strong SEO performance but only 17 citations',
        statValue: '17', statDelta: 'citations vs 19,700 impressions \u00b7 4.4% CTR', statDeltaColor: 'var(--warn)',
        chartType: 'donut', donutPct: 14, donutColor: 'var(--navy-2)', donutLabel: '14%',
        rootCauseTag: 'Strong SEO performance + low citations', rootCauseText: 'This page ranks well organically but lacks the structured data and direct-answer formatting AI engines favor when selecting sources to cite.',
        impactTag: 'Impact: Medium', impactText: 'Strong SEO performance isn\'t translating to AI citations, so this page\'s value is capped even as demand grows. Structured data work here can convert existing SEO equity into AI Citation Rate gains.',
        contributors: [{ label: 'Impressions', value: '19,700', pct: 'Strong', sub: 'via Search Console' }, { label: 'Citations', value: '17', pct: 'Low', sub: 'across 5 engines' }],
      },
      {
        id: 'ins_6', articleAction: 'draft', severity: 'High', severityBg: 'var(--neg-bg)', severityColor: 'var(--neg)', timeAgo: '5d',
        title: 'New content gap: competitors are cited for "geo vs seo strategy" prompts where Acme has partial coverage',
        statValue: '3', statDelta: 'competitor brands cited on this prompt cluster', statDeltaColor: 'var(--neg)',
        chartType: 'bar', barItems: [{ label: 'AthenaHQ', value: '5', h: '90%', color: 'var(--amber)' }, { label: 'Profound', value: '4', h: '70%', color: 'var(--amber)' }, { label: 'Scrunch AI', value: '2', h: '35%', color: 'var(--amber-light)' }, { label: 'Acme', value: '1', h: '18%', color: 'var(--muted)' }],
        rootCauseTag: 'Zero citations + competitor citations present', rootCauseText: 'AthenaHQ, Profound, and Scrunch AI are all cited on adjacent "geo vs seo" prompts — a dedicated comparison guide could close this gap.',
        impactTag: 'Impact: High', impactText: 'Competitors are actively winning the comparison narrative on a core positioning prompt cluster. New content here defends Share of Voice against AthenaHQ and Profound before the gap widens further.',
        contributors: [{ label: 'Prompt cluster', value: 'geo vs seo strategy', pct: '3', sub: 'competitors cited' }, { label: 'Engine', value: 'ChatGPT, Claude', pct: '2', sub: 'engines involved' }],
      },
      {
        id: 'ins_7', articleAction: 'update', severity: 'Medium', severityBg: 'var(--warn-bg)', severityColor: 'var(--warn)', timeAgo: '6d',
        title: 'Sentiment risk: mention rate is climbing on /case-study/acceldata while sentiment softens',
        statValue: '-6%', statDelta: 'sentiment vs prior, mentions up +9%', statDeltaColor: 'var(--neg)',
        chartType: 'hbar', hbarItems: [{ label: 'Mentions', value: '+9%', pct: '68%', color: 'var(--teal-deep)' }, { label: 'Sentiment', value: '-6%', pct: '38%', color: 'var(--neg)' }],
        rootCauseTag: 'Mentions up + sentiment down \u00b7 diverging trend', rootCauseText: 'AI engines are mentioning Acme more often on this case study, but responses increasingly frame it neutrally or with caveats — worth a messaging refresh.',
        impactTag: 'Impact: Medium', impactText: 'Rising mentions with softening sentiment can quietly erode brand perception even as visibility grows. A messaging refresh protects Sentiment Score from dragging down overall AEO Metrics.',
        contributors: [{ label: 'Engine', value: 'ChatGPT', pct: '54%', sub: 'of mentions' }, { label: 'Sentiment', value: 'Neutral drift', pct: '-6%', sub: 'vs prior period' }],
      },
      {
        id: 'ins_8', articleAction: 'draft', severity: 'Medium', severityBg: 'var(--warn-bg)', severityColor: 'var(--warn)', timeAgo: '6d',
        title: 'Engine concentration risk: 71% of all citations come from a single engine',
        statValue: '71%', statDelta: 'of citations from Google AI Overviews alone', statDeltaColor: 'var(--warn)',
        chartType: 'donut', donutPct: 71, donutColor: 'var(--teal-deep)', donutLabel: '71%',
        rootCauseTag: 'Single-engine dependency \u00b7 diversification opportunity', rootCauseText: 'Citation volume is heavily concentrated in one engine — an algorithm change there would disproportionately impact overall visibility. ChatGPT and Claude remain under-indexed.',
        impactTag: 'Impact: High', impactText: 'Heavy reliance on one engine leaves overall visibility exposed to a single algorithm change. Diversifying citation sources makes Visibility Score more resilient across the whole AEO Metrics set.',
        contributors: [{ label: 'Top engine', value: 'Google AI Overviews', pct: '71%', sub: 'of citations' }, { label: 'Under-indexed', value: 'Claude', pct: '8%', sub: 'citation share' }],
      },
      {
        id: 'ins_9', articleAction: 'update', severity: 'Low', severityBg: 'var(--teal-soft)', severityColor: 'var(--pos)', timeAgo: '1w',
        title: 'Stale content: /features/atlas holds a strong citation rate but hasn\u2019t been refreshed in over 6 months',
        statValue: '74', statDelta: 'citations \u00b7 last content update 6+ months ago', statDeltaColor: 'var(--steel)',
        chartType: 'hbar', hbarItems: [{ label: 'Avg pos 6mo ago', value: '2.4', pct: '85%', color: 'var(--teal-deep)' }, { label: 'Avg pos now', value: '3.1', pct: '62%', color: 'var(--teal-deep)' }],
        rootCauseTag: 'High citations + aging content \u00b7 refresh candidate', rootCauseText: 'AI engines still cite this page frequently, but its avg citation position has started slipping as competitors publish more current alternatives.',
        impactTag: 'Impact: Low', impactText: 'Citation position is slipping gradually — not urgent today, but compounding if left untouched. A refresh protects long-term Citation Rate and Avg. Position on an already-proven page.',
        contributors: [{ label: 'Citations', value: '74', pct: 'Strong', sub: 'across 1 engine' }, { label: 'Avg position', value: '3.1', pct: 'Slipping', sub: 'vs 2.4 6mo ago' }],
      },
      {
        id: 'ins_10', articleAction: 'draft', severity: 'Low', severityBg: 'var(--teal-soft)', severityColor: 'var(--pos)', timeAgo: '1w',
        title: 'Untapped engine: Claude has near-zero presence despite strong ChatGPT and Perplexity coverage',
        statValue: '8%', statDelta: 'citation share on Claude vs 52% combined on ChatGPT + Perplexity', statDeltaColor: 'var(--steel)',
        chartType: 'bar', barItems: [{ label: 'ChatGPT', value: '31%', h: '62%', color: 'var(--navy-2)' }, { label: 'Perplexity', value: '21%', h: '42%', color: 'var(--navy-2)' }, { label: 'Co-Pilot', value: '13%', h: '26%', color: 'var(--teal-deep)' }, { label: 'Claude', value: '8%', h: '16%', color: 'var(--navy)' }],
        rootCauseTag: 'Cross-engine gap \u00b7 expansion opportunity', rootCauseText: 'Content that performs well on ChatGPT and Perplexity isn\u2019t surfacing on Claude, suggesting a formatting or sourcing pattern Claude doesn\u2019t favor as readily.',
        impactTag: 'Impact: Low', impactText: 'Claude is a smaller but growing share of AI search traffic acme currently can\'t capture. Expanding here diversifies Share of Voice and reduces dependence on any single engine.',
        contributors: [{ label: 'Claude share', value: '8%', pct: 'Low', sub: 'of total citations' }, { label: 'ChatGPT + Perplexity', value: '52%', pct: 'High', sub: 'combined share' }],
      },
      {
        id: 'ins_11', articleAction: 'draft', severity: 'Medium', severityBg: 'var(--warn-bg)', severityColor: 'var(--warn)', timeAgo: '1w',
        title: 'Outreach opportunity: 3 unlinked mentions of Acme found on high-authority industry sites',
        statValue: '3', statDelta: 'unlinked brand mentions across AS 60+ domains', statDeltaColor: 'var(--warn)',
        chartType: 'bar', barItems: [{ label: 'searchengineland.com', value: 'AS 71', h: '85%', color: 'var(--teal-deep)' }, { label: 'reddit.com', value: 'AS 94', h: '100%', color: 'var(--teal-deep)' }, { label: 'g2.com', value: 'AS 91', h: '95%', color: 'var(--teal-deep)' }],
        rootCauseTag: 'Unlinked mentions \u00b7 outreach candidates', rootCauseText: 'These sites already mention Acme by name without linking or citing a source — a quick outreach email requesting a link or citation could convert these into trackable citations.',
        impactTag: 'Impact: Medium', impactText: 'Unlinked mentions on high-authority sites are citations left on the table with minimal outreach effort. Converting these into real citations lifts Citation Rate with very little content investment.',
        contributors: [{ label: 'Mentions found', value: '3', pct: 'New', sub: 'this month' }, { label: 'Avg authority', value: '85', pct: 'High', sub: 'across sites' }],
      },
      {
        id: 'ins_12', articleAction: 'draft', severity: 'Low', severityBg: 'var(--teal-soft)', severityColor: 'var(--pos)', timeAgo: '1w',
        title: 'Community opportunity: r/SEO and r/marketing threads discuss Acme without an official presence',
        statValue: '12', statDelta: 'active discussion threads mentioning Acme on Reddit', statDeltaColor: 'var(--steel)',
        chartType: 'donut', donutPct: 32, donutColor: 'var(--teal-deep)', donutLabel: '32%',
        rootCauseTag: 'Community mentions \u00b7 no official engagement yet', rootCauseText: 'AI engines increasingly cite Reddit threads directly in answers — engaging authentically in these communities could convert organic discussion into additional AI-visible citations.',
        impactTag: 'Impact: Low', impactText: 'AI engines increasingly surface Reddit threads directly, and Acme has no presence in an active conversation. Community engagement here builds Mention Rate and Citation Rate on a channel engines already trust.',
        contributors: [{ label: 'Threads found', value: '12', pct: 'r/SEO, r/marketing', sub: 'last 60 days' }, { label: 'Engine reliance', value: '32%', pct: 'Rising', sub: 'cite Reddit content' }],
      },
    ];
    const severityOrder = { High: 0, Medium: 1, Low: 2 };
    const tabs = tabDefs.map(t => ({
      label: t.label,
      badge: t.badge || false,
      onClick: () => this.setTab(t.key),
      color: s.activeTab === t.key ? '#fff' : 'rgba(242,241,236,0.65)',
      bg: s.activeTab === t.key ? 'rgba(255,255,255,0.08)' : 'transparent',
      dot: s.activeTab === t.key ? 'var(--amber)' : 'rgba(242,241,236,0.25)',
    }));
    const seoTabDefs = [
      { key: 'citations', label: 'Pages' },
      { key: 'proposed', label: 'Prompts', badge: 'Proposed' },
      { key: 'brand_keywords', label: 'Keywords' },
      { key: 'brand_competitors', label: 'Competitors' },
    ];
    const gscTabDefs = [
      { key: 'gsc_sitemaps', label: 'Sitemaps' },
      { key: 'seo_backlinks', label: 'Backlinks' },
    ];
    const brandTabDefs = [
      { key: 'brand_guidelines', label: 'Brand Guidelines' },
    ];
    const brandTabs = brandTabDefs.map(t => ({
      label: t.label, badge: t.badge || false, onClick: () => this.setTab(t.key),
      color: s.activeTab === t.key ? '#fff' : 'rgba(242,241,236,0.65)',
      bg: s.activeTab === t.key ? 'rgba(255,255,255,0.08)' : 'transparent',
      dot: s.activeTab === t.key ? 'var(--amber)' : 'rgba(242,241,236,0.25)',
    }));
    const seoTabs = seoTabDefs.map(t => ({
      label: t.label, onClick: () => this.setTab(t.key),
      color: s.activeTab === t.key ? '#fff' : 'rgba(242,241,236,0.65)',
      bg: s.activeTab === t.key ? 'rgba(255,255,255,0.08)' : 'transparent',
      dot: s.activeTab === t.key ? 'var(--teal-deep)' : 'rgba(242,241,236,0.25)',
    }));
    const gscTabs = gscTabDefs.map(t => ({
      label: t.label, onClick: () => this.setTab(t.key),
      color: s.activeTab === t.key ? '#fff' : 'rgba(242,241,236,0.65)',
      bg: s.activeTab === t.key ? 'rgba(255,255,255,0.08)' : 'transparent',
      dot: s.activeTab === t.key ? 'var(--navy-2)' : 'rgba(242,241,236,0.25)',
    }));
    const allTabDefs = [...tabDefs, ...seoTabDefs, ...gscTabDefs, ...brandTabDefs];
    const activeTabDef = allTabDefs.find(t => t.key === s.activeTab);
    const activeTabLabel = activeTabDef ? activeTabDef.label : 'Overview';

    const wizardSteps = [
      { n: 1, label: '1 · Keywords' }, { n: 2, label: '2 · Target' },
      { n: 3, label: '3 · Search settings' }, { n: 4, label: '4 · Review' },
    ].map(w => ({
      label: w.label, onClick: () => this.setState({ wizardStep: w.n }),
      bg: s.wizardStep === w.n ? 'var(--teal-soft)' : 'var(--line)',
      color: s.wizardStep === w.n ? 'var(--pos)' : 'var(--steel)',
      weight: s.wizardStep === w.n ? 700 : 600,
    }));

    const reportTabDefs = [
      { key: 'positions', label: 'Positions' }, { key: 'overview', label: 'Overview' },
      { key: 'landing', label: 'Landing pages' }, { key: 'comppages', label: "Competitors' pages" },
      { key: 'visibility', label: 'Tracking visibility' }, { key: 'config', label: 'Tracking overview' },
      { key: 'discovery', label: 'Competitors discovery' },
    ];
    const reportTabs = reportTabDefs.map(rt => ({
      label: rt.label, onClick: () => this.setState({ reportTab: rt.key }),
      bg: s.reportTab === rt.key ? 'var(--teal-soft)' : 'var(--line)',
      color: s.reportTab === rt.key ? 'var(--pos)' : 'var(--steel)',
      weight: s.reportTab === rt.key ? 700 : 500,
    }));

    const seoKeywordLookup = {};
    this.seoKeywords.forEach(k => { seoKeywordLookup[k.kw] = k; });
    const gscByKeyword = {
      'ai visibility tracking': { impressions: '65,200', clicks: '4,180', ctr: '6.4%' },
      'best aeo tools 2026': { impressions: '38,900', clicks: '1,920', ctr: '4.9%' },
      'acme ai visibility': { impressions: '9,400', clicks: '2,610', ctr: '27.8%' },
      'generative engine optimization': { impressions: '22,300', clicks: '1,340', ctr: '6.0%' },
      'ai search rank tracker': { impressions: '17,600', clicks: '640', ctr: '3.6%' },
      'chatgpt brand monitoring': { impressions: '11,900', clicks: '580', ctr: '4.9%' },
      'llm citation tracking': { impressions: '8,200', clicks: '390', ctr: '4.8%' },
      'ai overview optimization': { impressions: '7,100', clicks: '310', ctr: '4.4%' },
    };
    const keywordSearchQuery = (s.keywordSearchQuery || '').trim().toLowerCase();
    const trackedSeoKeywords = s.brandKeywords
      .filter(bk => !keywordSearchQuery || bk.keyword.toLowerCase().includes(keywordSearchQuery))
      .map(bk => {
        const seo = seoKeywordLookup[bk.keyword] || { kw: bk.keyword, url: '\u2014', pos: '\u2014', up: false, down: false, flat: true, change: 0, vol: '\u2014', value: '\u2014', kd: '\u2014', features: [] };
        const gsc = gscByKeyword[bk.keyword] || { impressions: '\u2014', clicks: '\u2014', ctr: '\u2014' };
        return { ...seo, ...gsc, keywordId: bk.id, onRemove: () => this.setState(st => ({ brandKeywords: st.brandKeywords.filter(x => x.id !== bk.id) })), onDetailedView: () => this.setState({ keywordInspectId: bk.id }) };
      });
    const keywordInspectRow = s.keywordInspectId ? trackedSeoKeywords.find(k => k.keywordId === s.keywordInspectId) : null;
    const keywordInspectPanel = keywordInspectRow ? { ...keywordInspectRow } : null;
    const brandKeywordRows = s.brandKeywords.map(bk => ({
      ...bk,
      onRemove: () => this.setState(st => ({ brandKeywords: st.brandKeywords.filter(x => x.id !== bk.id) })),
    }));
    const brandCompetitorRows = s.brandCompetitors.map(bc => ({
      ...bc,
      onRemove: () => this.setState(st => ({ brandCompetitors: st.brandCompetitors.filter(x => x.id !== bc.id) })),
    }));
    const recommendedKeywords = s.recommendedKeywords.map(r => ({
      text: r.text,
      onAdd: () => {
        const id = uid('kw');
        this.setState(st => ({
          brandKeywords: [...st.brandKeywords, { id, keyword: r.text }],
          recommendedKeywords: st.recommendedKeywords.filter(x => x.id !== r.id),
        }));
      },
    }));
    const recommendedCompetitors = s.recommendedCompetitors.map(r => ({
      domain: r.domain,
      onAdd: () => {
        const id = uid('bc');
        this.setState(st => ({
          brandCompetitors: [...st.brandCompetitors, { id, domain: r.domain }],
          recommendedCompetitors: st.recommendedCompetitors.filter(x => x.id !== r.id),
        }));
      },
    }));
    const recommendedGuidelines = s.recommendedGuidelines.map(r => ({
      text: r.text,
      onAdd: () => {
        const id = uid('gn');
        this.setState(st => ({
          brandGuidanceNotes: [...st.brandGuidanceNotes, { id, text: r.text }],
          recommendedGuidelines: st.recommendedGuidelines.filter(x => x.id !== r.id),
        }));
      },
    }));
    const brandGuidanceRows = s.brandGuidanceNotes.map(n => ({
      ...n,
      onRemove: () => this.setState(st => ({ brandGuidanceNotes: st.brandGuidanceNotes.filter(x => x.id !== n.id) })),
    }));

    const copilotTitle = s.activeTab === 'brand_keywords' ? 'Keyword Copilot'
      : s.activeTab === 'brand_competitors' ? 'Competitor Copilot'
      : s.activeTab === 'brand_guidelines' ? 'Brand Copilot'
      : 'Prompt Copilot';

    const gscKpis = [
      { label: 'Average position', value: '14.2', delta: '▲ improved 1.8 vs prior period', deltaColor: 'var(--pos)' },
      { label: 'Average CTR', value: '3.1%', delta: '▼ 0.3pp vs prior period', deltaColor: 'var(--neg)' },
      { label: 'Total clicks', value: '128,412', delta: '▲ 12.4% vs prior period', deltaColor: 'var(--pos)' },
      { label: 'Total impressions', value: '4.2M', delta: '▲ 8.1% vs prior period', deltaColor: 'var(--pos)' },
    ];

    const kpiDefs = [
      { key: 'visibility_score', label: 'Visibility', value: '34%', trend: '+3.2 pts vs prior', trendColor: 'var(--pos)', definition: 'Overall visibility across tracked prompts, weighted by mention rate, position, and share of voice.' },
      { key: 'mention_rate', label: 'Mention rate', value: '58%', trend: '-2.4 pts vs prior', trendColor: 'var(--neg)', definition: 'Answers mentioning your brand divided by total answers (0-100%). Higher values mean greater visibility.' },
      { key: 'share_of_voice', label: 'Share of voice', value: '21%', trend: '+1.1 pts vs prior', trendColor: 'var(--pos)', definition: 'Answers mentioning your brand divided by answers mentioning your brand OR competitors (0-100%). Higher values mean you dominate the conversation relative to competitors.' },
      { key: 'citation_rate', label: 'Citation rate', value: '46%', trend: '+5.8 pts vs prior', trendColor: 'var(--pos)', definition: 'Answers citing your domain divided by total answers with at least one citation (0-100%). Higher values indicate greater authority. Multiple URLs from the same domain count as one.' },
      { key: 'sentiment', label: 'Sentiment', value: '82', trend: '+4 pts vs prior', trendColor: 'var(--pos)', definition: 'Positive mentions plus half of neutral mentions, divided by total brand mentions (0-100). Higher values indicate better sentiment in how AI platforms portray your brand.' },
      { key: 'avg_position', label: 'Avg. position', value: '2.4', trend: 'Steady', trendColor: 'var(--steel)', definition: 'Average position where your brand is mentioned in AI responses (1 = first mention, 2 = second, etc.). Lower values indicate earlier, more prominent mentions.' },
    ];
    const kpis = kpiDefs.map((k, i) => ({
      ...k,
      showTooltipLeft: s.activeInfoKpi === k.key && i < kpiDefs.length - 2,
      showTooltipRight: s.activeInfoKpi === k.key && i >= kpiDefs.length - 2,
      onInfoEnter: () => this.setState({ activeInfoKpi: k.key }),
      onInfoLeave: () => this.setState({ activeInfoKpi: null }),
    }));

    const engineData = [
      { engine: 'ChatGPT', visibility_score: '41%', mention_rate: '64%', share_of_voice: '26%', citation_rate: '52%', sentiment_score: '84', avg_position: '2.1', citation_share: '34%' },
      { engine: 'Perplexity', visibility_score: '38%', mention_rate: '59%', share_of_voice: '23%', citation_rate: '49%', sentiment_score: '80', avg_position: '2.3', citation_share: '27%' },
      { engine: 'Google AI Overviews', visibility_score: '29%', mention_rate: '52%', share_of_voice: '18%', citation_rate: '41%', sentiment_score: '78', avg_position: '2.8', citation_share: '18%' },
      { engine: 'Microsoft Co-Pilot', visibility_score: '27%', mention_rate: '49%', share_of_voice: '17%', citation_rate: '38%', sentiment_score: '81', avg_position: '3.0', citation_share: '13%' },
      { engine: 'Claude', visibility_score: '24%', mention_rate: '45%', share_of_voice: '15%', citation_rate: '36%', sentiment_score: '85', avg_position: '3.3', citation_share: '8%' },
    ];
    const engineRows = engineData.map(r => ({ ...r, color: ENGINE_COLORS[r.engine], visBarWidth: r.visibility_score }));

    const brandMetricsData = [
      { name: 'Acme', mentionRate: 58, citationRate: 46, shareOfVoice: 21, sentiment: 82, avgPosition: 2.4, isYou: true },
      { name: 'AthenaHQ', mentionRate: 64, citationRate: 51, shareOfVoice: 24, sentiment: 79, avgPosition: 2.1, isYou: false },
      { name: 'Profound', mentionRate: 49, citationRate: 39, shareOfVoice: 17, sentiment: 76, avgPosition: 3.0, isYou: false },
      { name: 'Peec AI', mentionRate: 41, citationRate: 33, shareOfVoice: 14, sentiment: 74, avgPosition: 3.6, isYou: false },
    ];
    const makeLeaderboard = (key, unit, lowerIsBetter) => {
      const sorted = [...brandMetricsData].sort((a, b) => lowerIsBetter ? a[key] - b[key] : b[key] - a[key]);
      return sorted.map((b, i) => ({ rank: i + 1, name: b.name, rowBg: b.isYou ? 'var(--teal-soft)' : 'transparent', value: unit === '%' ? b[key] + '%' : b[key] }));
    };
    const leaderboards = [
      { label: 'Mention Rate', rows: makeLeaderboard('mentionRate', '%', false) },
      { label: 'Citation Rate', rows: makeLeaderboard('citationRate', '%', false) },
      { label: 'Share of Voice', rows: makeLeaderboard('shareOfVoice', '%', false) },
      { label: 'Sentiment', rows: makeLeaderboard('sentiment', '', false) },
      { label: 'Average Position', rows: makeLeaderboard('avgPosition', '', true) },
    ];

    const sharedKwCols = ['you', 'summit', 'basecamp', 'ridgeline'];
    const sharedKwAvg = {};
    sharedKwCols.forEach(col => {
      const vals = this.sharedKeywords.map(k => k[col]);
      sharedKwAvg[col] = Math.round((vals.reduce((a, b) => a + b, 0) / vals.length) * 10) / 10;
    });
    const metricsByDomain = {
      'athenahq.ai': { as: 58, traffic: '41.2K', keywords: '5,910', backlinks: '28,400', mentionRate: '64%', citationRate: '51%', shareOfVoice: '24%', sentiment: '79', avgPosition: '2.1', sharedKwAvgPos: sharedKwAvg.summit },
      'tryprofound.com': { as: 44, traffic: '19.8K', keywords: '3,120', backlinks: '9,650', mentionRate: '49%', citationRate: '39%', shareOfVoice: '17%', sentiment: '76', avgPosition: '3.0', sharedKwAvgPos: sharedKwAvg.basecamp },
      'peec.ai': { as: 39, traffic: '12.4K', keywords: '2,240', backlinks: '6,180', mentionRate: '41%', citationRate: '33%', shareOfVoice: '14%', sentiment: '74', avgPosition: '3.6', sharedKwAvgPos: sharedKwAvg.ridgeline },
      'conductor.com': { as: 62, traffic: '58.9K', keywords: '8,240', backlinks: '34,700', mentionRate: '37%', citationRate: '29%', shareOfVoice: '19%', sentiment: '71', avgPosition: '4.2', sharedKwAvgPos: '6.8' },
      'semrush.com': { as: 79, traffic: '312K', keywords: '41,600', backlinks: '198,000', mentionRate: '52%', citationRate: '44%', shareOfVoice: '28%', sentiment: '77', avgPosition: '2.7', sharedKwAvgPos: '5.1' },
      'brightedge.com': { as: 55, traffic: '22.1K', keywords: '4,380', backlinks: '15,900', mentionRate: '31%', citationRate: '25%', shareOfVoice: '12%', sentiment: '73', avgPosition: '4.8', sharedKwAvgPos: '8.4' },
      'scrunchai.com': { as: 28, traffic: '4.6K', keywords: '890', backlinks: '2,140', mentionRate: '22%', citationRate: '19%', shareOfVoice: '8%', sentiment: '80', avgPosition: '3.4', sharedKwAvgPos: '9.7' },
      'airops.com': { as: 33, traffic: '7.2K', keywords: '1,410', backlinks: '3,860', mentionRate: '27%', citationRate: '21%', shareOfVoice: '10%', sentiment: '75', avgPosition: '3.1', sharedKwAvgPos: '7.9' },
    };
    const dash = { as: '\u2014', traffic: '\u2014', keywords: '\u2014', backlinks: '\u2014', mentionRate: '\u2014', citationRate: '\u2014', shareOfVoice: '\u2014', sentiment: '\u2014', avgPosition: '\u2014', sharedKwAvgPos: '\u2014' };
    const competitorSearchQ = (s.competitorSearchQuery || '').trim().toLowerCase();
    const consolidatedCompetitors = [
      { domain: 'Acme (you)', isYou: true, ...{ as: 47, traffic: '24.6K', keywords: '3,842', backlinks: '12,842', mentionRate: '58%', citationRate: '46%', shareOfVoice: '21%', sentiment: '82', avgPosition: '2.4', sharedKwAvgPos: sharedKwAvg.you }, sharedKwCount: this.sharedKeywords.length, onRemove: null },
      ...s.brandCompetitors.map(bc => ({
        domain: bc.domain, isYou: false,
        ...(metricsByDomain[bc.domain] || dash),
        sharedKwCount: metricsByDomain[bc.domain] ? this.sharedKeywords.length : '\u2014',
        onRemove: () => this.setState(st => ({ brandCompetitors: st.brandCompetitors.filter(x => x.id !== bc.id) })),
      })),
    ].filter(r => !competitorSearchQ || r.domain.toLowerCase().includes(competitorSearchQ)).map(r => ({ ...r, rowBg: r.isYou ? 'var(--teal-soft)' : 'transparent' }));

    const competingBrands = [
      { name: 'AthenaHQ', note: '+8.4%', noteColor: 'var(--pos)' },
      { name: 'Profound', note: '+5.1%', noteColor: 'var(--pos)' },
      { name: 'Peec AI', note: '+2.6%', noteColor: 'var(--pos)' },
      { name: 'Conductor', note: '-1.3%', noteColor: 'var(--neg)' },
      { name: 'Semrush', note: '+0.9%', noteColor: 'var(--pos)' },
      { name: 'Brightedge', note: '-3.2%', noteColor: 'var(--neg)' },
      { name: 'Scrunch AI', note: '-0.4%', noteColor: 'var(--neg)' },
      { name: 'AirOps', note: '+1.7%', noteColor: 'var(--pos)' },
    ];

    // Mentions are keyed by their content, not by position in the filtered
    // list — a positional key silently points at a different mention (or at
    // nothing) as soon as the engine filter changes underneath an open drawer.
    const mentionKey = (p) => `${p.ai_engine}|${p.date}|${p.prompt_text}`;
    const allMentions = this.allPrompts.map(p => ({ ...p, ai_engine: normalizeEngine(p.ai_engine) }));
    const filteredList = allMentions.filter(p => s.engineFilter === 'all' || p.ai_engine === s.engineFilter);
    const toMentionRow = (p) => ({
      mentionKey: mentionKey(p),
      prompt_text: p.prompt_text,
      ai_engine: p.ai_engine,
      response_excerpt: p.response_excerpt,
      position: p.position ?? '—',
      sentiment: p.sentiment,
      dateLabel: new Date(p.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }),
      citationCount: p.citation_urls.length,
      engineColor: ENGINE_COLORS[p.ai_engine] || 'var(--muted)',
      mentionedLabel: p.mentioned ? 'Mentioned' : 'Not mentioned',
      mentionedPillClass: p.mentioned ? 'pill pill-teal' : 'pill pill-neg',
      onSelect: () => this.setState({ selectedMentionKey: mentionKey(p) }),
    });
    const filteredPrompts = filteredList.map(toMentionRow);

    // Resolved against the *unfiltered* set so the drawer keeps showing the
    // mention the user actually opened.
    const selectedMentionSource = s.selectedMentionKey
      ? allMentions.find(p => mentionKey(p) === s.selectedMentionKey)
      : null;
    const selectedMentionBase = selectedMentionSource ? toMentionRow(selectedMentionSource) : null;
    const selectedMention = selectedMentionBase ? {
      ...selectedMentionBase,
      mentionRatePct: selectedMentionBase.mentionedLabel === 'Mentioned' ? '100%' : '0%',
    } : null;
    const mentionCompetitorRows = s.brandCompetitors.map((bc, i) => ({
      name: bc.domain, rate: i === 0 ? '18%' : i === 1 ? '11%' : '0%',
    }));
    const mentionPlatformRows = Object.keys(ENGINE_COLORS).map(name => ({
      name, color: ENGINE_COLORS[name],
      rate: selectedMention && selectedMention.ai_engine === name && selectedMention.mentionedLabel === 'Mentioned' ? '100%' : '0%',
    }));
    const paidSovRows = s.brandCompetitors.map(bc => ({ name: bc.domain, sov: '0.0%' }));
    const answerHistoryRows = selectedMention ? [
      { date: 'Jul 28, 2026', persona: 'Default', platform: selectedMention.ai_engine, preview: selectedMention.response_excerpt.slice(0, 40) + '…', cited: selectedMention.citationCount > 0, mentioned: selectedMention.mentionedLabel === 'Mentioned', hasAds: false },
    ] : [];

    const ga4KpiDefs = [
      { label: 'Users', value: '48.2K', trend: '+12.4% vs prior period', trendColor: 'var(--pos)' },
      { label: 'Sessions', value: '71.9K', trend: '+8.1% vs prior period', trendColor: 'var(--pos)' },
      { label: 'Engagement rate', value: '64%', trend: '+3.1pt vs prior period', trendColor: 'var(--pos)' },
      { label: 'Conversions', value: '1,842', trend: '+9.6% vs prior period', trendColor: 'var(--pos)' },
      { label: 'Revenue', value: '$96,410', trend: '-2.8% vs prior period', trendColor: 'var(--neg)' },
    ];
    const ga4Kpis = ga4KpiDefs.map(g => ({ ...g, hasTrend: !!g.trend }));

    const pageDetailByPath = {
      'www.acme.com/blog-post/athena-vs-semrush': { sessions: '5,240', users: '4,080', engagement: '66%', conv: '301', revenue: '$11,860', delta: '+21%', deltaColor: 'var(--pos)' },
      'www.acme.com/case-study/acceldata': { sessions: '2,910', users: '2,510', engagement: '46%', conv: '58', revenue: '$1,340', delta: '-16%', deltaColor: 'var(--neg)', usersDelta: '-12%' },
      'www.acme.com/features/atlas': { sessions: '3,880', users: '2,940', engagement: '61%', conv: '164', revenue: '$6,120', delta: '+14%', deltaColor: 'var(--pos)' },
      'www.acme.com/report/state-of-aeo-2026': { sessions: '4,120', users: '3,210', engagement: '58%', conv: '212', revenue: '$8,940', delta: '+12%', deltaColor: 'var(--pos)' },
      'www.acme.com/guide/geo-vs-seo-explained': { sessions: '2,760', users: '2,190', engagement: '54%', conv: '87', revenue: '$3,420', delta: '+16%', deltaColor: 'var(--pos)', usersDelta: '+15%' },
      'www.acme.com/blog-post/how-ai-overviews-work': { sessions: '3,340', users: '2,650', engagement: '49%', conv: '102', revenue: '$4,180', delta: '-11%', deltaColor: 'var(--neg)' },
      'www.acme.com/case-study/northwind-retail': { sessions: '1,980', users: '1,540', engagement: '52%', conv: '64', revenue: '$2,860', delta: '+18%', deltaColor: 'var(--pos)' },
      'www.acme.com/features/prompt-tracking': { sessions: '2,410', users: '1,970', engagement: '57%', conv: '93', revenue: '$3,910', delta: '+13%', deltaColor: 'var(--pos)' },
      'www.acme.com/blog-post/citation-rate-benchmarks': { sessions: '1,620', users: '1,280', engagement: '44%', conv: '31', revenue: '$1,150', delta: '-14%', deltaColor: 'var(--neg)' },
      'www.acme.com/report/competitor-share-of-voice': { sessions: '1,340', users: '1,050', engagement: '41%', conv: '22', revenue: '$860', delta: '+11%', deltaColor: 'var(--pos)' },
    };

    const gscPageDetailByUrl = {
      'www.acme.com/blog-post/athena-vs-semrush': { clicks: '4,180', impressions: '65,200', ctr: '6.4%', position: '3.2' },
      'www.acme.com/case-study/acceldata': { clicks: '1,920', impressions: '46,800', ctr: '4.1%', position: '7.6', ctrDelta: '-13%' },
      'www.acme.com/features/atlas': { clicks: '2,640', impressions: '50,700', ctr: '5.2%', position: '5.9', posDelta: '+12%' },
      'www.acme.com/report/state-of-aeo-2026': { clicks: '3,050', impressions: '52,600', ctr: '5.8%', position: '4.4', imprDelta: '+19%' },
      'www.acme.com/guide/geo-vs-seo-explained': { clicks: '2,110', impressions: '39,400', ctr: '5.4%', position: '6.1' },
      'www.acme.com/blog-post/how-ai-overviews-work': { clicks: '2,480', impressions: '44,900', ctr: '5.5%', position: '5.3', clicksDelta: '-17%' },
      'www.acme.com/case-study/northwind-retail': { clicks: '1,340', impressions: '28,600', ctr: '4.7%', position: '7.8' },
      'www.acme.com/features/prompt-tracking': { clicks: '1,790', impressions: '33,200', ctr: '5.4%', position: '6.6' },
      'www.acme.com/blog-post/citation-rate-benchmarks': { clicks: '1,020', impressions: '22,300', ctr: '4.6%', position: '9.1', posDelta: '-11%' },
      'www.acme.com/report/competitor-share-of-voice': { clicks: '860', impressions: '19,700', ctr: '4.4%', position: '9.6', ctrDelta: '+14%' },
    };

    const citations = this.citationsData.map(c => {
      const ga4 = pageDetailByPath[c.url] || { sessions: '—', users: '—', engagement: '—', conv: '—', revenue: '—', delta: '—', deltaColor: 'var(--steel)' };
      const gsc = gscPageDetailByUrl[c.url] || { clicks: '—', impressions: '—', ctr: '—', position: '—' };
      return {
        ...c,
        changeColor: c.change_vs_previous && c.change_vs_previous.startsWith('-') ? 'var(--neg)' : 'var(--pos)',
        hasChange: !!c.change_vs_previous,
        hasAvgPosDelta: !!c.avgPosDelta,
        avgPosDeltaColor: c.avgPosDelta && c.avgPosDelta.startsWith('-') ? 'var(--neg)' : 'var(--pos)',
        enginesList: c.engines.map(normalizeEngine).join(', '),
        ga4Sessions: ga4.sessions, ga4Users: ga4.users, ga4Engagement: ga4.engagement,
        ga4Conv: ga4.conv, ga4Revenue: ga4.revenue, ga4Delta: ga4.delta, ga4DeltaColor: ga4.deltaColor,
        hasUsersDelta: !!ga4.usersDelta, usersDelta: ga4.usersDelta,
        usersDeltaColor: ga4.usersDelta && ga4.usersDelta.startsWith('-') ? 'var(--neg)' : 'var(--pos)',
        gscClicks: gsc.clicks, gscImpressions: gsc.impressions, gscCtr: gsc.ctr, gscPosition: gsc.position,
        hasPosDelta: !!gsc.posDelta, posDelta: gsc.posDelta,
        posDeltaColor: gsc.posDelta && gsc.posDelta.startsWith('-') ? 'var(--neg)' : 'var(--pos)',
        hasImprDelta: !!gsc.imprDelta, imprDelta: gsc.imprDelta,
        imprDeltaColor: gsc.imprDelta && gsc.imprDelta.startsWith('-') ? 'var(--neg)' : 'var(--pos)',
        hasClicksDelta: !!gsc.clicksDelta, clicksDelta: gsc.clicksDelta,
        clicksDeltaColor: gsc.clicksDelta && gsc.clicksDelta.startsWith('-') ? 'var(--neg)' : 'var(--pos)',
        hasCtrDelta: !!gsc.ctrDelta, ctrDelta: gsc.ctrDelta,
        ctrDeltaColor: gsc.ctrDelta && gsc.ctrDelta.startsWith('-') ? 'var(--neg)' : 'var(--pos)',
        menuOpen: s.openRowMenuUrl === c.url,
        toggleMenu: () => this.setState(st => ({ openRowMenuUrl: st.openRowMenuUrl === c.url ? null : c.url })),
        onDetailedView: () => this.setState({ openRowMenuUrl: null, inspectUrl: c.url }),
      };
    });

    const indexStatusByUrl = {
      'www.acme.com/blog-post/athena-vs-semrush': { verdict: 'PASS', coverageState: 'Submitted and indexed', robotsTxtState: 'ALLOWED', indexingState: 'INDEXING_ALLOWED', lastCrawlTime: '2 days ago', pageFetchState: 'SUCCESSFUL', googleCanonical: 'www.acme.com/blog-post/athena-vs-semrush', userCanonical: 'www.acme.com/blog-post/athena-vs-semrush', sitemap: ['sitemap-posts.xml'], referringUrls: ['acme.com/blog', 'acme.com/resources', '+12 more'] },
      'www.acme.com/case-study/acceldata': { verdict: 'PASS', coverageState: 'Submitted and indexed', robotsTxtState: 'ALLOWED', indexingState: 'INDEXING_ALLOWED', lastCrawlTime: '4 days ago', pageFetchState: 'SUCCESSFUL', googleCanonical: 'www.acme.com/case-study/acceldata', userCanonical: 'www.acme.com/case-study/acceldata', sitemap: ['sitemap-case-studies.xml'], referringUrls: ['acme.com/customers', '+6 more'] },
      'www.acme.com/features/atlas': { verdict: 'PARTIAL', coverageState: 'Crawled - currently not indexed', robotsTxtState: 'ALLOWED', indexingState: 'INDEXING_ALLOWED', lastCrawlTime: '9 days ago', pageFetchState: 'SUCCESSFUL', googleCanonical: 'www.acme.com/features/atlas', userCanonical: 'www.acme.com/features/atlas', sitemap: ['sitemap-features.xml'], referringUrls: ['acme.com/product', '+3 more'] },
      'www.acme.com/report/state-of-aeo-2026': { verdict: 'PASS', coverageState: 'Submitted and indexed', robotsTxtState: 'ALLOWED', indexingState: 'INDEXING_ALLOWED', lastCrawlTime: '1 day ago', pageFetchState: 'SUCCESSFUL', googleCanonical: 'www.acme.com/report/state-of-aeo-2026', userCanonical: 'www.acme.com/report/state-of-aeo-2026', sitemap: ['sitemap-reports.xml'], referringUrls: ['acme.com/resources', 'acme.com/blog', '+18 more'] },
    };
    const defaultIndexStatus = { verdict: 'PASS', coverageState: 'Submitted and indexed', robotsTxtState: 'ALLOWED', indexingState: 'INDEXING_ALLOWED', lastCrawlTime: '5 days ago', pageFetchState: 'SUCCESSFUL', googleCanonical: '', userCanonical: '', sitemap: ['sitemap.xml'], referringUrls: ['—'] };

    const inspectRow = s.inspectUrl ? citations.find(c => c.url === s.inspectUrl) : null;
    const inspectEngineRows = s.citationsEngineFilter === 'all' ? engineRows : engineRows.filter(r => r.engine === s.citationsEngineFilter);
    const citationRateKpi = kpis.find(k => k.key === 'citation_rate');
    const avgPositionKpi = kpis.find(k => k.key === 'avg_position');
    const inspectSummaryCards = inspectRow ? [
      { label: 'Citations', value: String(inspectRow.citations_count), trend: inspectRow.change_vs_previous || '', trendColor: inspectRow.changeColor },
      { label: citationRateKpi.label, value: citationRateKpi.value, trend: citationRateKpi.trend, trendColor: citationRateKpi.trendColor },
      { label: avgPositionKpi.label, value: avgPositionKpi.value, trend: avgPositionKpi.trend, trendColor: avgPositionKpi.trendColor },
    ] : [];
    const rawIndexStatus = inspectRow ? (indexStatusByUrl[inspectRow.url] || { ...defaultIndexStatus, googleCanonical: inspectRow.url, userCanonical: inspectRow.url }) : null;
    const verdictColors = { PASS: { bg: 'var(--teal-soft)', color: 'var(--pos)' }, PARTIAL: { bg: 'var(--warn-bg)', color: 'var(--warn)' }, FAIL: { bg: 'var(--neg-bg)', color: 'var(--neg)' }, NEUTRAL: { bg: 'var(--cloud)', color: 'var(--steel)' } };
    const indexStatus = rawIndexStatus ? { ...rawIndexStatus, verdictBg: verdictColors[rawIndexStatus.verdict].bg, verdictColor: verdictColors[rawIndexStatus.verdict].color, sitemapList: rawIndexStatus.sitemap.join(', '), referringUrlsList: rawIndexStatus.referringUrls.join(', '), inspectionResultLink: 'https://search.google.com/search-console/inspect?resource_id=' + encodeURIComponent(inspectRow.url) } : null;
    const inspectPanel = inspectRow ? { ...inspectRow, kpis: inspectSummaryCards, engineRows: inspectEngineRows, topPrompts: s.trackedPrompts.slice(0, 5), trafficSpark: this.sparkPoints(inspectRow.url + 'traffic', 200, 40), ctrSpark: this.sparkPoints(inspectRow.url + 'ctr', 200, 40), indexStatus } : null;

    const topicOrder = s.topics.map(t => t.id);
    const q = s.searchQuery.trim().toLowerCase();
    const visiblePrompts = s.trackedPrompts
      .filter(t => !q || t.prompt_text.toLowerCase().includes(q))
      .map(t => ({
        ...NEW_PROMPT_METRICS,
        ...t,
        topicName: this.topicName(s.topics, t.topicId),
        topicColor: TOPIC_COLORS[t.topicId] || 'var(--muted)',
        volumeLabel: this.volumeLabel(t.promptVolume),
        mentionTrendColor: this.trendColor(t.mentionTrend),
        citationTrendColor: this.trendColor(t.citationTrend),
        shareOfVoice: this.shareOfVoice(t.mentionRate),
        sovTrend: pts((parseFloat(t.mentionTrend) || 0) * 0.5),
        sovTrendColor: this.trendColor(t.mentionTrend),
        promptTypePillClass: t.promptType === 'Brand Related' ? 'pill pill-info' : 'pill pill-neutral',
        onRemove: () => this.setState(st => ({ trackedPrompts: st.trackedPrompts.filter(x => x.prompt_id !== t.prompt_id) })),
        onDetailedView: () => this.setState({ promptInspectId: t.prompt_id }),
      }));

    const promptInspectRow = s.promptInspectId ? s.trackedPrompts.find(t => t.prompt_id === s.promptInspectId) : null;
    const promptInspectPanel = promptInspectRow ? {
      ...NEW_PROMPT_METRICS,
      ...promptInspectRow,
      topicName: this.topicName(s.topics, promptInspectRow.topicId),
      engineRows,
      volumeLabel: this.volumeLabel(promptInspectRow.promptVolume),
      mentionTrendColor: this.trendColor(promptInspectRow.mentionTrend),
      citationTrendColor: this.trendColor(promptInspectRow.citationTrend),
      topCompetitors: competingBrands.slice(0, 3),
      sovByCompetitor: (() => {
        const acmeSov = parseInt(this.shareOfVoice(promptInspectRow.mentionRate), 10);
        const rows = [{ name: 'Acme (you)', sov: acmeSov + '%', isYou: true }];
        competingBrands.slice(0, 4).forEach((b, i) => {
          const seed = (acmeSov + (i + 1) * 7) % 40 + 5;
          rows.push({ name: b.name, sov: seed + '%', isYou: false });
        });
        return rows.sort((a, b) => parseFloat(b.sov) - parseFloat(a.sov)).map((r, i) => ({ ...r, rank: i + 1, rowBg: r.isYou ? 'var(--teal-soft)' : 'transparent' }));
      })(),
    } : null;

    const recommendedFromPlatform = s.recommendedFromPlatform.map(r => ({
      text: r.text,
      topicName: this.topicName(s.topics, r.topicId),
      onAdd: () => {
        const id = uid('pt');
        this.setState(st => ({
          trackedPrompts: [...st.trackedPrompts, { ...NEW_PROMPT_METRICS, prompt_id: id, topicId: r.topicId, prompt_text: r.text }],
          recommendedFromPlatform: st.recommendedFromPlatform.filter(x => x.id !== r.id),
        }));
      },
    }));

    const recoPrompts = {
      id: 'reco_prompts', severity: 'High', severityBg: 'var(--neg-bg)', severityColor: 'var(--neg)', timeAgo: 'New', isReco: true,
      title: 'Recommended prompts to track based on competitor and category coverage',
      reasonText: 'These prompts are already surfacing competitor brands in AI answers within your tracked topics — adding them closes visibility blind spots before a competitor cements the top citation.',
      items: recommendedFromPlatform.map(r => ({ label: '"' + r.text + '"', sublabel: r.topicName, onAdd: r.onAdd })),
    };
    const recoKeywords = {
      id: 'reco_keywords', severity: 'Medium', severityBg: 'var(--warn-bg)', severityColor: 'var(--warn)', timeAgo: 'New', isReco: true,
      title: 'Recommended keywords based on your category and competitor coverage',
      reasonText: 'Tracked competitors already rank for these terms — adding them to your keyword set lets you monitor both traditional SEO position and AI citation performance side by side.',
      items: recommendedKeywords.map(r => ({ label: '"' + r.text + '"', sublabel: '', onAdd: r.onAdd })),
    };
    const recoCompetitors = {
      id: 'reco_competitors', severity: 'Medium', severityBg: 'var(--warn-bg)', severityColor: 'var(--warn)', timeAgo: 'New', isReco: true,
      title: 'Recommended competitors showing up frequently alongside your brand',
      reasonText: 'These domains keep appearing next to Acme in AI answers but aren\u2019t in your tracked set yet — adding them gives you a complete picture of relative share of voice.',
      items: recommendedCompetitors.map(r => ({ label: r.domain, sublabel: '', onAdd: r.onAdd })),
    };
    // Severity ordering is applied to the real insights FIRST, then the three
    // recommendation cards are woven in at fixed slots. Sorting the merged list
    // instead — as this previously did — discarded the interleave entirely.
    const insightsBySeverity = [...insightsRaw].sort((a, b) => severityOrder[a.severity] - severityOrder[b.severity]);
    const insightsMerged = [];
    const recoQueue = [recoPrompts, recoKeywords, recoCompetitors];
    insightsBySeverity.forEach((ins, i) => {
      insightsMerged.push(ins);
      // After every second insight, surface the next recommendation card.
      if (i % 2 === 1 && recoQueue.length) insightsMerged.push(recoQueue.shift());
    });
    insightsMerged.push(...recoQueue);

    const insights = insightsMerged.map(i => ({
      ...i,
      isNotReco: !i.isReco,
      onViewDetails: () => this.setState({ insightDetailId: i.id }),
      articleActionIsUpdate: !i.isReco && i.articleAction === 'update',
      articleActionIsDraft: !i.isReco && i.articleAction !== 'update',
      isLine: i.chartType === 'line', isBar: i.chartType === 'bar', isDonut: i.chartType === 'donut', isHbar: i.chartType === 'hbar',
      donutGradient: i.chartType === 'donut' ? `conic-gradient(${i.donutColor} ${i.donutPct * 3.6}deg, var(--line) 0deg)` : '',
      onDraft: () => this.setState({ insightDraftId: i.id }),
    }));
    const insightDraftInsight = s.insightDraftId ? insights.find(i => i.id === s.insightDraftId) : null;
    const insightDetailRow = s.insightDetailId ? insights.find(i => i.id === s.insightDetailId) : null;
    const insightDetailPanel = insightDetailRow ? {
      title: insightDetailRow.title,
      rootCauseTag: insightDetailRow.rootCauseTag,
      rootCauseText: insightDetailRow.rootCauseText,
      statValue: insightDetailRow.statValue,
      statDelta: insightDetailRow.statDelta,
      statDeltaColor: insightDetailRow.statDeltaColor,
      severity: insightDetailRow.severity,
      severityBg: insightDetailRow.severityBg,
      severityColor: insightDetailRow.severityColor,
      impactText: insightDetailRow.impactText,
      contributors: insightDetailRow.contributors || [],
      isLine: insightDetailRow.isLine, isBar: insightDetailRow.isBar,
      isDonut: insightDetailRow.isDonut, isHbar: insightDetailRow.isHbar,
      chartLine1: insightDetailRow.chartLine1, chartLine2: insightDetailRow.chartLine2, chartColor: insightDetailRow.chartColor,
      barItems: insightDetailRow.barItems || [], hbarItems: insightDetailRow.hbarItems || [],
      donutGradient: insightDetailRow.donutGradient, donutLabel: insightDetailRow.donutLabel,
      timeline: [
        { period: '3 weeks ago', value: 'Baseline', note: 'Metric within expected range' },
        { period: '2 weeks ago', value: 'First signal', note: 'Deviation detected against prior period' },
        { period: 'Last week', value: 'Confirmed', note: 'Trend sustained across multiple engines' },
        { period: 'This week', value: insightDetailRow.statValue, note: insightDetailRow.statDelta },
      ],
    } : null;
    const insightDraftPanel = insightDraftInsight ? {
      title: insightDraftInsight.title,
      articleTitle: insightDraftInsight.isReco ? insightDraftInsight.title.replace('Recommended ', '').replace(/^\w/, c => c.toUpperCase()) : insightDraftInsight.title.split(':').pop().trim(),
      draftParagraphs: (() => {
        const articleBodies = {
          ins_2: [
            'Acme gives teams a single place to see how their brand shows up across ChatGPT, Perplexity, Google AI Overviews, Microsoft Copilot, and Claude — and, just as importantly, what it costs to get there.',
            'Pricing starts with a Starter plan built for teams tracking a single brand and a handful of competitors, scales to a Growth plan with expanded prompt and keyword tracking, and tops out with an Enterprise plan that adds custom reporting, SSO, and dedicated support.',
            'Unlike point solutions that cover either traditional SEO or AI visibility, every plan includes both — so Search Console data, keyword rankings, and AI citation tracking live in one dashboard instead of three.',
            'Compared to AthenaHQ and Profound, Acme is positioned for teams who don\u2019t want to run separate tools for SEO and AEO: one login, one price, one view of how content performs everywhere it\u2019s discovered.',
          ],
          ins_6: [
            'GEO (Generative Engine Optimization) and SEO (Search Engine Optimization) share a common goal — getting found — but they optimize for different judges.',
            'Traditional SEO optimizes for ranking algorithms: keywords, backlinks, page speed, and crawlability, judged by whether a page appears on page one of Google.',
            'GEO optimizes for how AI engines like ChatGPT, Perplexity, and Google AI Overviews select, summarize, and cite sources when answering a user\u2019s question directly — success looks like being the source an AI engine quotes, not just a blue link.',
            'In practice, that means GEO content leans harder on clear, quotable claims, structured data, and directly answering the question a prompt is likely to ask — while still benefiting from the technical foundations good SEO already provides.',
          ],
          ins_8: [
            'Right now, a majority of Acme\u2019s AI citations come from a single engine — Google AI Overviews — which means a single algorithm change there has an outsized effect on overall visibility.',
            'ChatGPT and Claude, by contrast, are under-indexed relative to their share of AI search usage, suggesting Acme\u2019s content isn\u2019t yet formatted in a way those engines favor when selecting sources.',
            'This piece breaks down what each major AI engine tends to prioritize when citing sources, and what a more balanced, multi-engine content strategy looks like in practice.',
          ],
          ins_10: [
            'Claude increasingly favors sources with clear reasoning, direct comparisons, and well-labeled data over purely promotional copy — a different bar than ChatGPT or Perplexity apply.',
            'This guide walks through how Claude tends to select and cite sources, and outlines the specific formatting and sourcing changes that could help Acme content surface more often in Claude-powered answers.',
          ],
          ins_11: [
            'Outreach draft — subject: "Quick source note on your recent piece"',
            'Hi team, we noticed your recent piece mentions Acme by name — thank you for that! We\u2019d love to make it easy for readers to learn more: would you be open to linking the mention to our site, or citing the specific data point referenced?',
            'Happy to share supporting stats, a quote from our team, or any additional context that would be useful. Let me know what\u2019s easiest on your end.',
          ],
          ins_12: [
            'Community post draft — r/SEO / r/marketing',
            'We\u2019ve seen a few threads here asking about AI visibility tracking for brands, so wanted to jump in and share some context from the trenches (not trying to sell anything — just adding to the discussion).',
            'Happy to answer questions on how AEO tracking works differently from traditional rank tracking, or share what we\u2019ve learned monitoring citations across ChatGPT, Perplexity, and Google AI Overviews.',
          ],
        };
        if (insightDraftInsight.isReco) {
          return [
            `Draft outline covering ${insightDraftInsight.items ? insightDraftInsight.items.length : 0} recommended items, written to close the gap identified in this insight.`,
            insightDraftInsight.reasonText || '',
          ];
        }
        return articleBodies[insightDraftInsight.id] || [insightDraftInsight.rootCauseText || 'Draft content addressing the pattern identified in this insight, ready for review before publishing.'];
      })(),
      isUpdate: !insightDraftInsight.isReco && insightDraftInsight.articleAction === 'update',
      changeSummary: insightDraftInsight.impactTag ? `Why it changed: ${insightDraftInsight.rootCauseText}` : '',
      changes: !insightDraftInsight.isReco && insightDraftInsight.articleAction === 'update' ? (({
        ins_1: [
          { label: 'Updated section', detail: 'Refreshed the "how AI Overviews selects sources" section with current examples and a clearer summary paragraph AI engines can quote directly.' },
          { label: 'Added', detail: 'A comparison callout showing how this guide differs from competitor coverage, to re-earn the citation Google AI Overviews dropped.' },
          { label: 'Why', detail: insightDraftInsight.rootCauseText },
        ],
        ins_3: [
          { label: 'Updated section', detail: 'Expanded the AEO industry-trends data with the latest quarter\u2019s figures to keep the report current as both citations and impressions climb.' },
          { label: 'Added', detail: 'A new subsection highlighting the metrics driving this report\u2019s growth, to reinforce why it\u2019s being cited more often.' },
          { label: 'Why', detail: insightDraftInsight.rootCauseText },
        ],
        ins_4: [
          { label: 'Updated section', detail: 'Rewrote the page title and meta description to lead with the specific citation-rate benchmark number, matching what searchers are looking for.' },
          { label: 'Added', detail: 'A summary table near the top of the page so both readers and AI engines can extract the key benchmark at a glance.' },
          { label: 'Why', detail: insightDraftInsight.rootCauseText },
        ],
        ins_5: [
          { label: 'Updated section', detail: 'Added FAQ-style structured data (schema.org markup) around the competitor share-of-voice comparison already on the page.' },
          { label: 'Added', detail: 'A direct-answer summary paragraph at the top of the page formatted the way AI engines prefer to extract and cite.' },
          { label: 'Why', detail: insightDraftInsight.rootCauseText },
        ],
        ins_7: [
          { label: 'Updated section', detail: 'Softened absolute claims in the Acceldata case study and added a specific, sourced outcome metric to reinforce credibility.' },
          { label: 'Added', detail: 'A short customer-quote callout to shift sentiment back toward positive framing in AI-generated summaries.' },
          { label: 'Why', detail: insightDraftInsight.rootCauseText },
        ],
        ins_9: [
          { label: 'Updated section', detail: 'Refreshed the Atlas feature overview with current screenshots and this year\u2019s product capabilities.' },
          { label: 'Added', detail: 'A "last updated" date and changelog note, both of which AI engines weight when judging content freshness.' },
          { label: 'Why', detail: insightDraftInsight.rootCauseText },
        ],
      })[insightDraftInsight.id] || [
        { label: 'Updated section', detail: 'Refreshed the section most tied to this insight\u2019s root cause, aligned to current citation and search-performance data.' },
        { label: 'Added', detail: 'New supporting data points and structure to address the gap identified above.' },
        { label: 'Why', detail: insightDraftInsight.rootCauseText },
      ]) : [],
    } : null;
    if (insightDraftPanel) insightDraftPanel.isDraftMode = !insightDraftPanel.isUpdate;

    const copilotSuggestions = s.copilotSuggestions.map(sug => ({
      text: sug.text,
      topicName: this.topicName(s.topics, sug.topicId),
      onAdd: () => {
        const id = uid('pt');
        this.setState(st => ({
          trackedPrompts: [...st.trackedPrompts, { ...NEW_PROMPT_METRICS, prompt_id: id, topicId: sug.topicId, prompt_text: sug.text }],
          copilotSuggestions: st.copilotSuggestions.filter(x => x.id !== sug.id),
        }));
      },
    }));

    const topicsDraft = s.topicsDraft.map((td, i) => ({
      name: td.name,
      onChange: (e) => this.setState(st => { const arr = [...st.topicsDraft]; arr[i] = { ...arr[i], name: e.target.value }; return { topicsDraft: arr }; }),
      onDelete: () => this.setState(st => ({ topicsDraft: st.topicsDraft.filter((_, idx) => idx !== i) })),
    }));

    return {
      tabs, activeTabLabel, seoTabs, gscTabs, brandTabs,
      isBrandKeywords: s.activeTab === 'brand_keywords',
      isBrandCompetitors: s.activeTab === 'brand_competitors',
      isBrandGuidelines: s.activeTab === 'brand_guidelines',
      brandKeywordRows, trackedSeoKeywords,
      keywordInspectPanel, closeKeywordInspect: () => this.setState({ keywordInspectId: null }),
      keywordSearchQuery: s.keywordSearchQuery,
      onKeywordSearchChange: (e) => this.setState({ keywordSearchQuery: e.target.value }),
      showAddKeywordForm: s.showAddKeywordForm,
      toggleAddKeywordForm: () => this.setState(st => ({ showAddKeywordForm: !st.showAddKeywordForm })),
      competitorSearchQuery: s.competitorSearchQuery,
      onCompetitorSearchChange: (e) => this.setState({ competitorSearchQuery: e.target.value }),
      competitorsDateFrom: s.competitorsDateFrom,
      onCompetitorsDateFromChange: (e) => this.setState({ competitorsDateFrom: e.target.value }),
      competitorsDateTo: s.competitorsDateTo,
      onCompetitorsDateToChange: (e) => this.setState({ competitorsDateTo: e.target.value }),
      competitorsRegionFilter: s.competitorsRegionFilter,
      onCompetitorsRegionFilterChange: (e) => this.setState({ competitorsRegionFilter: e.target.value }),
      competitorsPlatformFilter: s.competitorsPlatformFilter,
      onCompetitorsPlatformFilterChange: (e) => this.setState({ competitorsPlatformFilter: e.target.value }),
      showRefreshConfig: s.showRefreshConfig,
      toggleRefreshConfig: () => this.setState(st => ({ showRefreshConfig: !st.showRefreshConfig })),
      refreshFrequency: s.refreshFrequency,
      onRefreshFrequencyChange: (e) => this.setState({ refreshFrequency: e.target.value }),
      newKeywordText: s.newKeywordText,
      onNewKeywordChange: (e) => this.setState({ newKeywordText: e.target.value }),
      addBrandKeyword: () => {
        if (!s.newKeywordText.trim()) return;
        const id = uid('kw');
        this.setState(st => ({ brandKeywords: [...st.brandKeywords, { id, keyword: st.newKeywordText.trim() }], newKeywordText: '', showAddKeywordForm: false }));
      },
      brandCompetitorRows,
      newCompetitorText: s.newCompetitorText,
      onNewCompetitorChange: (e) => this.setState({ newCompetitorText: e.target.value }),
      addBrandCompetitor: () => {
        if (!s.newCompetitorText.trim()) return;
        const id = uid('bc');
        this.setState(st => ({ brandCompetitors: [...st.brandCompetitors, { id, domain: st.newCompetitorText.trim() }], newCompetitorText: '' }));
      },
      isOverview: s.activeTab === 'overview',
      isInsights: s.activeTab === 'insights',
      insights, insightDraftPanel,
      insightDetailPanel, closeInsightDetail: () => this.setState({ insightDetailId: null }),
      pepperRequested: s.pepperRequested,
      pepperNotRequested: !s.pepperRequested,
      requestPepperHelp: () => this.setState({ pepperRequested: true }),
      closeInsightDraft: () => this.setState({ insightDraftId: null, insightPublished: false }),
      insightPublished: s.insightPublished,
      publishInsightDraft: () => this.setState({ insightPublished: true }),
      isCitations: s.activeTab === 'citations',
      isProposed: s.activeTab === 'proposed',
      isSeoBacklinks: s.activeTab === 'seo_backlinks',
      isSeoReports: s.activeTab === 'seo_reports',
      isGscOverview: s.activeTab === 'gsc_overview',
      isGscSitemaps: s.activeTab === 'gsc_sitemaps',
      seoCompetitors: this.seoCompetitors, movers: this.movers, seoKeywords: this.seoKeywords,
      backlinkDomains: this.backlinkDomains, trackedKeywords: this.trackedKeywords,
      landingPages: this.landingPages, competitorPages: this.competitorPages,
      discovered: this.discovered, compRows: this.compRows, sharedKeywords: this.sharedKeywords,
      wizardSteps, wizardStepIs1: s.wizardStep === 1, wizardStepIs2: s.wizardStep === 2,
      wizardStepIs3: s.wizardStep === 3, wizardStepIs4: s.wizardStep === 4,
      reportTabs,
      reportTabIsPositions: s.reportTab === 'positions', reportTabIsOverview: s.reportTab === 'overview',
      reportTabIsLanding: s.reportTab === 'landing', reportTabIsCompPages: s.reportTab === 'comppages',
      reportTabIsVisibility: s.reportTab === 'visibility', reportTabIsConfig: s.reportTab === 'config',
      reportTabIsDiscovery: s.reportTab === 'discovery',
      gscKpis, gscQueries: this.gscQueries, gscPages: this.gscPages,
      inspections: this.inspections, sitemaps: this.sitemaps,
      kpis, engineRows, competingBrands, ga4Kpis, leaderboards, consolidatedCompetitors,
      inspectPanel, closeInspectPanel: () => this.setState({ inspectUrl: null }),
      marketingFilter: s.marketingFilter,
      onMarketingFilterChange: (e) => this.setState({ marketingFilter: e.target.value }),
      overviewTimeRange: s.overviewTimeRange,
      onOverviewTimeRangeChange: (e) => this.setState({ overviewTimeRange: e.target.value }),
      gscCountryFilter: s.gscCountryFilter,
      onGscCountryFilterChange: (e) => this.setState({ gscCountryFilter: e.target.value }),
      gscTimeRangeFilter: s.gscTimeRangeFilter,
      onGscTimeRangeFilterChange: (e) => this.setState({ gscTimeRangeFilter: e.target.value }),
      gscDeviceFilter: s.gscDeviceFilter,
      onGscDeviceFilterChange: (e) => this.setState({ gscDeviceFilter: e.target.value }),
      citationsCountryFilter: s.citationsCountryFilter,
      onCitationsCountryFilterChange: (e) => this.setState({ citationsCountryFilter: e.target.value }),
      citationsTimeRangeFilter: s.citationsTimeRangeFilter,
      onCitationsTimeRangeFilterChange: (e) => this.setState({ citationsTimeRangeFilter: e.target.value }),
      citationsDeviceFilter: s.citationsDeviceFilter,
      onCitationsDeviceFilterChange: (e) => this.setState({ citationsDeviceFilter: e.target.value }),
      citationsEngineFilter: s.citationsEngineFilter,
      onCitationsEngineFilterChange: (e) => this.setState({ citationsEngineFilter: e.target.value }),
      promptsDateFrom: s.promptsDateFrom,
      onPromptsDateFromChange: (e) => this.setState({ promptsDateFrom: e.target.value }),
      promptsDateTo: s.promptsDateTo,
      onPromptsDateToChange: (e) => this.setState({ promptsDateTo: e.target.value }),
      promptsRegionFilter: s.promptsRegionFilter,
      onPromptsRegionFilterChange: (e) => this.setState({ promptsRegionFilter: e.target.value }),
      promptsPlatformFilter: s.promptsPlatformFilter,
      onPromptsPlatformFilterChange: (e) => this.setState({ promptsPlatformFilter: e.target.value }),
      keywordsDateFrom: s.keywordsDateFrom,
      onKeywordsDateFromChange: (e) => this.setState({ keywordsDateFrom: e.target.value }),
      keywordsDateTo: s.keywordsDateTo,
      onKeywordsDateToChange: (e) => this.setState({ keywordsDateTo: e.target.value }),
      keywordsRegionFilter: s.keywordsRegionFilter,
      onKeywordsRegionFilterChange: (e) => this.setState({ keywordsRegionFilter: e.target.value }),
      keywordsPlatformFilter: s.keywordsPlatformFilter,
      onKeywordsPlatformFilterChange: (e) => this.setState({ keywordsPlatformFilter: e.target.value }),
      stopPropagation: (e) => e.stopPropagation(),
      engineFilter: s.engineFilter,
      onEngineFilterChange: (e) => this.setState({ engineFilter: e.target.value }),
      dateFrom: s.dateFrom,
      onDateFromChange: (e) => this.setState({ dateFrom: e.target.value }),
      dateTo: s.dateTo,
      onDateToChange: (e) => this.setState({ dateTo: e.target.value }),
      showDatePicker: s.showDatePicker,
      toggleDatePicker: () => this.setState(st => ({ showDatePicker: !st.showDatePicker })),
      // Clamped: a "To" earlier than "From" must not read "Last -12 days".
      dateRangeLabel: (() => {
        const days = Math.round((new Date(s.dateTo) - new Date(s.dateFrom)) / 86400000);
        if (!Number.isFinite(days) || days < 0) return 'Custom range';
        if (days === 0) return 'Today';
        return `Last ${days} day${days === 1 ? '' : 's'}`;
      })(),
      // Bound the pickers to each other so the invalid state is unreachable.
      dateFromMax: s.dateTo,
      dateToMin: s.dateFrom,
      filteredPrompts, noPrompts: filteredPrompts.length === 0,
      selectedMention, hasSelectedMention: !!selectedMention,
      closeMention: () => this.setState({ selectedMentionKey: null }),
      mentionCompetitorRows, mentionPlatformRows, paidSovRows, answerHistoryRows,
      citations,
      topics: s.topics,
      trackedCount: s.trackedPrompts.length,
      topicCount: topicOrder.length,
      searchQuery: s.searchQuery,
      onSearchChange: (e) => this.setState({ searchQuery: e.target.value }),
      visiblePrompts, noVisiblePrompts: visiblePrompts.length === 0,
      promptInspectPanel, closePromptInspect: () => this.setState({ promptInspectId: null }),
      promptsSubTab: s.promptsSubTab,
      isYourPrompts: s.promptsSubTab === 'yours',
      isRecommended: s.promptsSubTab === 'recommended',
      isMentions: s.promptsSubTab === 'mentions',
      selectYourPrompts: () => this.setState({ promptsSubTab: 'yours' }),
      selectRecommended: () => this.setState({ promptsSubTab: 'recommended' }),
      selectMentions: () => this.setState({ promptsSubTab: 'mentions' }),
      yourPromptsColor: s.promptsSubTab === 'yours' ? 'var(--text)' : 'var(--steel)',
      yourPromptsBorder: s.promptsSubTab === 'yours' ? 'var(--teal-deep)' : 'transparent',
      recommendedColor: s.promptsSubTab === 'recommended' ? 'var(--text)' : 'var(--steel)',
      recommendedBorder: s.promptsSubTab === 'recommended' ? 'var(--teal-deep)' : 'transparent',
      mentionsColor: s.promptsSubTab === 'mentions' ? 'var(--text)' : 'var(--steel)',
      mentionsBorder: s.promptsSubTab === 'mentions' ? 'var(--teal-deep)' : 'transparent',
      recommendedFromPlatform, noRecommended: recommendedFromPlatform.length === 0,
      hasRecommendedFromPlatform: recommendedFromPlatform.length > 0,
      showAddForm: s.showAddForm,
      toggleAddForm: () => this.setState(st => ({ showAddForm: !st.showAddForm })),
      newPromptText: s.newPromptText,
      onNewPromptChange: (e) => this.setState({ newPromptText: e.target.value }),
      newPromptTopicId: s.newPromptTopicId,
      isAddingNewTopic: s.newPromptTopicId === '__new__',
      onNewPromptTopicChange: (e) => this.setState({ newPromptTopicId: e.target.value }),
      newTopicName: s.newTopicName,
      onNewTopicNameChange: (e) => this.setState({ newTopicName: e.target.value }),
      addPrompt: () => {
        if (!s.newPromptText.trim()) return;
        let topicId = s.newPromptTopicId;
        let topics = s.topics;
        if (topicId === '__new__') {
          const name = s.newTopicName.trim() || 'Uncategorized';
          topicId = uid('topic');
          topics = [...topics, { id: topicId, name }];
        }
        const id = uid('pt');
        this.setState(st => ({
          topics,
          trackedPrompts: [...st.trackedPrompts, { ...NEW_PROMPT_METRICS, prompt_id: id, topicId, prompt_text: st.newPromptText.trim() }],
          newPromptText: '', newTopicName: '', showAddForm: false,
        }));
      },
      showEditTopics: s.showEditTopics,
      topicsDraft,
      toggleEditTopics: () => this.setState(st => ({
        showEditTopics: !st.showEditTopics,
        topicsDraft: !st.showEditTopics ? st.topics.map(t => ({ id: t.id, name: t.name })) : st.topicsDraft,
      })),
      addTopicDraft: () => this.setState(st => ({ topicsDraft: [...st.topicsDraft, { id: uid('topic'), name: '' }] })),
      saveTopics: () => this.setState(st => ({
        topics: st.topicsDraft.filter(t => t.name.trim()),
        showEditTopics: false,
      })),
      copilotOpen: s.copilotOpen,
      copilotTitle,
      toggleCopilot: () => this.setState(st => ({ copilotOpen: !st.copilotOpen })),
      copilotSuggestions, noCopilotSuggestions: copilotSuggestions.length === 0,
      copilotInput: s.copilotInput,
      onCopilotInputChange: (e) => this.setState({ copilotInput: e.target.value }),
      askCopilot: () => {
        if (!s.copilotInput.trim()) return;
        const text = s.copilotInput.trim();
        this.setState(st => {
          if (st.activeTab === 'brand_keywords') return { recommendedKeywords: [...st.recommendedKeywords, { id: uid('rk'), text }], copilotInput: '' };
          if (st.activeTab === 'brand_competitors') return { recommendedCompetitors: [...st.recommendedCompetitors, { id: uid('rc'), domain: text }], copilotInput: '' };
          if (st.activeTab === 'brand_guidelines') return { recommendedGuidelines: [...st.recommendedGuidelines, { id: uid('rg'), text }], copilotInput: '' };
          const id = uid('cs');
          return { copilotSuggestions: [...st.copilotSuggestions, { id, topicId: st.topics[0] ? st.topics[0].id : 'topic_seo', text: `${text} — recommended by AI overviews` }], copilotInput: '' };
        });
      },
      recommendedKeywords, hasRecommendedKeywords: recommendedKeywords.length > 0,
      recommendedCompetitors, hasRecommendedCompetitors: recommendedCompetitors.length > 0,
      recommendedGuidelines, hasRecommendedGuidelines: recommendedGuidelines.length > 0,
      brandGuidanceRows,
      newGuidanceText: s.newGuidanceText,
      onNewGuidanceChange: (e) => this.setState({ newGuidanceText: e.target.value }),
      addGuidanceNote: () => {
        if (!s.newGuidanceText.trim()) return;
        const id = uid('gn');
        this.setState(st => ({ brandGuidanceNotes: [...st.brandGuidanceNotes, { id, text: st.newGuidanceText.trim() }], newGuidanceText: '' }));
      },
    };
  }
}
