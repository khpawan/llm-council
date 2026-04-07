import { useState, useEffect } from 'react';
import { api } from '../api';
import './Settings.css';

const ALGORITHM_OPTIONS = [
  { value: 'peer_review', label: 'Peer Review' },
  { value: 'consensus_only', label: 'Consensus Only' },
  { value: 'chairman_only', label: 'Chairman Only' },
  { value: 'red_team', label: 'Red Team' },
  { value: 'audience_split', label: 'Audience Split' },
  { value: 'claim_evidence', label: 'Claim Evidence' },
];

const ALGORITHM_DESCRIPTIONS = {
  peer_review: 'Full 3-stage flow: collect answers, have models review each other, then synthesize a final response.',
  consensus_only: 'Collect first-pass answers and synthesize them directly, skipping peer review.',
  chairman_only: 'Send the prompt straight to the chairman model for the fastest single-model answer.',
  red_team: 'Run peer review with a stronger focus on weaknesses, risks, failure modes, and missing safeguards.',
  audience_split: 'Review answers for different audiences, such as leadership, security, and product or operations.',
  claim_evidence: 'Review answers by checking which claims are supported, weakly supported, or unsupported.',
};

const RANKING_DESCRIPTIONS = {
  average_rank: 'Average Rank: lower is better. This is the simplest score and easiest to read.',
  borda: 'Borda Count: higher is better. This rewards responses that are consistently ranked near the top.',
};

export default function Settings({ onBackToChat }) {
  const [provider, setProvider] = useState('openrouter');
  const [azureEndpoint, setAzureEndpoint] = useState('');
  const [azureApiKey, setAzureApiKey] = useState('');
  const [azureApiVersion, setAzureApiVersion] = useState('');
  const [openrouterApiKey, setOpenrouterApiKey] = useState('');
  const [deployments, setDeployments] = useState([]);
  const [modelRoutes, setModelRoutes] = useState([]);
  const [algorithmRoutes, setAlgorithmRoutes] = useState([]);
  const [councilModels, setCouncilModels] = useState([]);
  const [chairmanModel, setChairmanModel] = useState('');
  const [algorithm, setAlgorithm] = useState('peer_review');
  const [rankingAggregation, setRankingAggregation] = useState('average_rank');
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState(null);

  useEffect(() => {
    async function loadConfig() {
      try {
        const config = await api.getConfig();
        setProvider(config.llm_provider || 'openrouter');
        setAzureEndpoint(config.azure_foundry_endpoint || '');
        setAzureApiKey(config.azure_foundry_api_key || '');
        setAzureApiVersion(config.azure_foundry_api_version || '');
        setOpenrouterApiKey(config.openrouter_api_key || '');
        setAlgorithm(config.council_algorithm || 'peer_review');
        setRankingAggregation(config.rank_aggregation_method || 'average_rank');
        setChairmanModel(config.chairman_model || '');

        const deploymentMap = config.azure_foundry_deployment_map || {};
        const endpointMap = config.azure_foundry_endpoint_map || {};
        const apiKeyMap = config.azure_foundry_api_key_map || {};
        const algorithmEndpointMap = config.azure_foundry_algorithm_endpoint_map || {};
        const algorithmApiKeyMap = config.azure_foundry_algorithm_api_key_map || {};
        const models = config.council_models || [];

        if (Object.keys(deploymentMap).length > 0) {
          setDeployments(
            Object.entries(deploymentMap).map(([name, model]) => ({ name, model }))
          );
        } else if (models.length > 0) {
          setDeployments(models.map((model) => ({ name: model, model })));
        } else {
          setDeployments([]);
        }

        setModelRoutes(
          Array.from(
            new Set([
              ...Object.keys(endpointMap),
              ...Object.keys(apiKeyMap),
            ])
          ).map((name) => ({
            name,
            endpoint: endpointMap[name] || '',
            apiKey: apiKeyMap[name] || '',
          }))
        );

        setAlgorithmRoutes(
          Array.from(
            new Set([
              ...Object.keys(algorithmEndpointMap),
              ...Object.keys(algorithmApiKeyMap),
            ])
          ).map((routeAlgorithm) => ({
            algorithm: routeAlgorithm,
            endpoint: algorithmEndpointMap[routeAlgorithm] || '',
            apiKey: algorithmApiKeyMap[routeAlgorithm] || '',
          }))
        );

        setCouncilModels(config.council_models || []);
      } catch {
        showToast('Failed to load configuration', 'error');
      } finally {
        setLoading(false);
      }
    }

    void loadConfig();
  }, []);

  useEffect(() => {
    if (toast) {
      const timer = setTimeout(() => setToast(null), 3000);
      return () => clearTimeout(timer);
    }
  }, [toast]);

  function showToast(message, type = 'success') {
    setToast({ message, type });
  }

  function addDeployment() {
    setDeployments([...deployments, { name: '', model: '' }]);
  }

  function addModelRoute() {
    setModelRoutes([...modelRoutes, { name: '', endpoint: '', apiKey: '' }]);
  }

  function removeModelRoute(index) {
    setModelRoutes(modelRoutes.filter((_, i) => i !== index));
  }

  function updateModelRoute(index, field, value) {
    const updated = [...modelRoutes];
    updated[index] = { ...updated[index], [field]: value };
    setModelRoutes(updated);
  }

  function addAlgorithmRoute() {
    setAlgorithmRoutes([
      ...algorithmRoutes,
      { algorithm: 'peer_review', endpoint: '', apiKey: '' },
    ]);
  }

  function removeAlgorithmRoute(index) {
    setAlgorithmRoutes(algorithmRoutes.filter((_, i) => i !== index));
  }

  function updateAlgorithmRoute(index, field, value) {
    const updated = [...algorithmRoutes];
    updated[index] = { ...updated[index], [field]: value };
    setAlgorithmRoutes(updated);
  }

  function removeDeployment(index) {
    const updated = deployments.filter((_, i) => i !== index);
    setDeployments(updated);
    // Clean up council models that reference removed deployment
    const remainingNames = new Set(updated.map((d) => d.name));
    setCouncilModels(councilModels.filter((m) => remainingNames.has(m)));
    if (!remainingNames.has(chairmanModel)) {
      setChairmanModel('');
    }
  }

  function updateDeployment(index, field, value) {
    const updated = [...deployments];
    const oldName = updated[index].name;
    updated[index] = { ...updated[index], [field]: value };
    if (provider !== 'azure_foundry' && field === 'name') {
      updated[index].model = value;
    }
    setDeployments(updated);

    if (field === 'name' && oldName !== value) {
      setCouncilModels(councilModels.map((m) => (m === oldName ? value : m)));
      if (chairmanModel === oldName) {
        setChairmanModel(value);
      }
    }
  }

  function toggleCouncilModel(name) {
    if (councilModels.includes(name)) {
      setCouncilModels(councilModels.filter((m) => m !== name));
    } else {
      setCouncilModels([...councilModels, name]);
    }
  }

  function assembleConfig() {
    const config = {
      llm_provider: provider,
      council_models: councilModels,
      chairman_model: chairmanModel,
      council_algorithm: algorithm,
      rank_aggregation_method: rankingAggregation,
    };

    if (provider === 'azure_foundry') {
      config.azure_foundry_endpoint = azureEndpoint;
      config.azure_foundry_api_key = azureApiKey;
      config.azure_foundry_api_version = azureApiVersion;
      const deploymentMap = {};
      const endpointMap = {};
      const apiKeyMap = {};
      const algorithmEndpointMap = {};
      const algorithmApiKeyMap = {};

      for (const d of deployments) {
        if (d.name) {
          deploymentMap[d.name] = d.model;
        }
      }

      for (const route of modelRoutes) {
        if (!route.name) {
          continue;
        }
        if (route.endpoint) {
          endpointMap[route.name] = route.endpoint;
        }
        if (route.apiKey) {
          apiKeyMap[route.name] = route.apiKey;
        }
      }

      for (const route of algorithmRoutes) {
        if (!route.algorithm) {
          continue;
        }
        if (route.endpoint) {
          algorithmEndpointMap[route.algorithm] = route.endpoint;
        }
        if (route.apiKey) {
          algorithmApiKeyMap[route.algorithm] = route.apiKey;
        }
      }

      config.azure_foundry_deployment_map = deploymentMap;
      config.azure_foundry_endpoint_map = endpointMap;
      config.azure_foundry_api_key_map = apiKeyMap;
      config.azure_foundry_algorithm_endpoint_map = algorithmEndpointMap;
      config.azure_foundry_algorithm_api_key_map = algorithmApiKeyMap;
    } else {
      config.openrouter_api_key = openrouterApiKey;
    }

    return config;
  }

  async function handleSave() {
    try {
      await api.saveConfig(assembleConfig());
      showToast('Configuration saved successfully', 'success');
    } catch {
      showToast('Failed to save configuration', 'error');
    }
  }

  async function handleTest() {
    try {
      const result = await api.testConfig(assembleConfig());
      if (result.status === 'ok') {
        showToast('Connection test passed', 'success');
      } else {
        showToast(result.message || 'Connection test failed', 'error');
      }
    } catch {
      showToast('Connection test failed', 'error');
    }
  }

  if (loading) {
    return (
      <div className="settings-page">
        <div className="settings-content">
          <p>Loading configuration...</p>
        </div>
      </div>
    );
  }

  const deploymentNames = deployments.map((d) => d.name).filter(Boolean);

  return (
    <div className="settings-page">
      <div className="settings-content">
        <div className="settings-header">
          <h2 className="settings-title">Settings</h2>
          {onBackToChat && (
            <button className="btn-outline settings-back-btn" onClick={onBackToChat}>
              Back to Chat
            </button>
          )}
        </div>

        {/* Provider Section */}
        <section className="settings-section">
          <h3>Provider</h3>
          <label className="settings-label">Active Provider</label>
          <select
            className="settings-select"
            value={provider}
            onChange={(e) => setProvider(e.target.value)}
          >
            <option value="openrouter">OpenRouter</option>
            <option value="azure_foundry">Azure Foundry</option>
          </select>
        </section>

        {/* Azure Foundry Connection */}
        {provider === 'azure_foundry' && (
          <section className="settings-section">
            <h3>Default Azure Foundry Project</h3>
            <p className="settings-hint settings-section-hint">
              This is the default project used unless a more specific model or algorithm route sends the request elsewhere.
            </p>
            <label className="settings-label">Endpoint URL</label>
            <input
              type="text"
              className="settings-input"
              value={azureEndpoint}
              onChange={(e) => setAzureEndpoint(e.target.value)}
              placeholder="https://your-resource.services.ai.azure.com"
            />
            <label className="settings-label">API Key</label>
            <input
              type="password"
              className="settings-input"
              value={azureApiKey}
              onChange={(e) => setAzureApiKey(e.target.value)}
              placeholder="Enter your Azure API key"
            />
            <label className="settings-label">API Version</label>
            <input
              type="text"
              className="settings-input"
              value={azureApiVersion}
              onChange={(e) => setAzureApiVersion(e.target.value)}
              placeholder="2024-12-01-preview"
            />
          </section>
        )}

        {provider === 'azure_foundry' && (
          <section className="settings-section">
            <h3>Use Alternate Project For Specific Models</h3>
            <p className="settings-hint settings-section-hint">
              Use this when one model needs a different Foundry project than the default, such as a region-specific deployment.
            </p>
            {modelRoutes.length === 0 && (
              <p className="settings-hint">No model-specific alternate project routes configured.</p>
            )}
            {modelRoutes.map((route, index) => (
              <div key={index} className="route-row">
                <input
                  type="text"
                  className="settings-input route-name-input"
                  value={route.name}
                  onChange={(e) => updateModelRoute(index, 'name', e.target.value)}
                  placeholder="Model label"
                />
                <input
                  type="text"
                  className="settings-input"
                  value={route.endpoint}
                  onChange={(e) => updateModelRoute(index, 'endpoint', e.target.value)}
                  placeholder="Endpoint URL"
                />
                <input
                  type="password"
                  className="settings-input"
                  value={route.apiKey}
                  onChange={(e) => updateModelRoute(index, 'apiKey', e.target.value)}
                  placeholder="API key"
                />
                <button
                  className="btn-remove"
                  onClick={() => removeModelRoute(index)}
                  title="Remove model override"
              >
                &times;
              </button>
            </div>
          ))}
          <button className="btn-add" onClick={addModelRoute}>
            + Add Model Route
          </button>
        </section>
      )}

      {provider === 'azure_foundry' && (
        <section className="settings-section">
          <h3>Use Alternate Project For Specific Algorithms</h3>
          <p className="settings-hint settings-section-hint">
            Use this when an entire algorithm should run on another Foundry project. Model-specific routes still take priority.
          </p>
          {algorithmRoutes.length === 0 && (
            <p className="settings-hint">No algorithm-specific alternate project routes configured.</p>
          )}
            {algorithmRoutes.map((route, index) => (
              <div key={index} className="route-row">
                <select
                  className="settings-select route-algorithm-select"
                  value={route.algorithm}
                  onChange={(e) => updateAlgorithmRoute(index, 'algorithm', e.target.value)}
                >
                  {ALGORITHM_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
                <input
                  type="text"
                  className="settings-input"
                  value={route.endpoint}
                  onChange={(e) => updateAlgorithmRoute(index, 'endpoint', e.target.value)}
                  placeholder="Endpoint URL"
                />
                <input
                  type="password"
                  className="settings-input"
                  value={route.apiKey}
                  onChange={(e) => updateAlgorithmRoute(index, 'apiKey', e.target.value)}
                  placeholder="API key"
                />
                <button
                  className="btn-remove"
                  onClick={() => removeAlgorithmRoute(index)}
                  title="Remove algorithm override"
              >
                &times;
              </button>
            </div>
          ))}
          <button className="btn-add" onClick={addAlgorithmRoute}>
            + Add Algorithm Route
          </button>
        </section>
      )}

        {/* OpenRouter Connection */}
        {provider === 'openrouter' && (
          <section className="settings-section">
            <h3>OpenRouter Connection</h3>
            <label className="settings-label">API Key</label>
            <input
              type="password"
              className="settings-input"
              value={openrouterApiKey}
              onChange={(e) => setOpenrouterApiKey(e.target.value)}
              placeholder="Enter your OpenRouter API key"
            />
          </section>
        )}

        {/* Deployments Section */}
        <section className="settings-section">
          <h3>{provider === 'azure_foundry' ? 'Model Mappings' : 'Models'}</h3>
          {deployments.map((dep, index) => (
            <div key={index} className="deployment-row">
              <input
                type="text"
                className="settings-input deployment-input"
                value={dep.name}
                onChange={(e) => updateDeployment(index, 'name', e.target.value)}
                placeholder={provider === 'azure_foundry' ? 'Model label' : 'Model ID'}
              />
              {provider === 'azure_foundry' && (
                <input
                  type="text"
                  className="settings-input deployment-input"
                  value={dep.model}
                  onChange={(e) => updateDeployment(index, 'model', e.target.value)}
                  placeholder="Deployment name"
                />
              )}
              <button
                className="btn-remove"
                onClick={() => removeDeployment(index)}
                title={provider === 'azure_foundry' ? 'Remove mapping' : 'Remove model'}
              >
                &times;
              </button>
            </div>
          ))}
          <button className="btn-add" onClick={addDeployment}>
            + Add {provider === 'azure_foundry' ? 'Model Mapping' : 'Model'}
          </button>
        </section>

        {/* Council Configuration */}
        <section className="settings-section">
          <h3>Council Configuration</h3>
          <label className="settings-label">Council Members</label>
          <div className="council-checkboxes">
            {deploymentNames.map((name) => (
              <label key={name} className="checkbox-label">
                <input
                  type="checkbox"
                  checked={councilModels.includes(name)}
                  onChange={() => toggleCouncilModel(name)}
                />
                {name}
              </label>
            ))}
            {deploymentNames.length === 0 && (
              <p className="settings-hint">
                Add {provider === 'azure_foundry' ? 'model mappings' : 'models'} above to configure council members.
              </p>
            )}
          </div>
          <label className="settings-label">Chairman Model</label>
          <select
            className="settings-select"
            value={chairmanModel}
            onChange={(e) => setChairmanModel(e.target.value)}
          >
            <option value="">Select chairman...</option>
            {deploymentNames.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        </section>

        {/* Defaults Section */}
        <section className="settings-section">
          <h3>Defaults</h3>
          <label className="settings-label">Algorithm</label>
        <select
          className="settings-select"
          value={algorithm}
          onChange={(e) => setAlgorithm(e.target.value)}
        >
            {ALGORITHM_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          <p className="settings-hint settings-section-hint">
            {ALGORITHM_DESCRIPTIONS[algorithm]}
          </p>
          <label className="settings-label">Ranking Aggregation</label>
          <select
            className="settings-select"
            value={rankingAggregation}
            onChange={(e) => setRankingAggregation(e.target.value)}
          >
            <option value="average_rank">Average Rank</option>
            <option value="borda">Borda Count</option>
          </select>
          <p className="settings-hint settings-section-hint">
            {RANKING_DESCRIPTIONS[rankingAggregation]}
          </p>
        </section>

        {/* Actions */}
        <div className="settings-actions">
          <button className="btn-primary" onClick={handleSave}>
            Save Configuration
          </button>
          <button className="btn-outline" onClick={handleTest}>
            Test Connection
          </button>
        </div>

        {/* Toast */}
        {toast && (
          <div className={`settings-toast toast-${toast.type}`}>
            {toast.message}
          </div>
        )}
      </div>
    </div>
  );
}
