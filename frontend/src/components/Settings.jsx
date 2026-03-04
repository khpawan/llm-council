import { useState, useEffect } from 'react';
import { api } from '../api';
import './Settings.css';

export default function Settings({ onBackToChat }) {
  const [provider, setProvider] = useState('openrouter');
  const [azureEndpoint, setAzureEndpoint] = useState('');
  const [azureApiKey, setAzureApiKey] = useState('');
  const [azureApiVersion, setAzureApiVersion] = useState('');
  const [openrouterApiKey, setOpenrouterApiKey] = useState('');
  const [deployments, setDeployments] = useState([]);
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
        const models = config.council_models || [];

        if (Object.keys(deploymentMap).length > 0) {
          setDeployments(
            Object.entries(deploymentMap).map(([name, model]) => ({ name, model }))
          );
        } else if (models.length > 0) {
          setDeployments(models.map((model) => ({ name: model, model })));
        }

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
      for (const d of deployments) {
        if (d.name) {
          deploymentMap[d.name] = d.model;
        }
      }
      config.azure_foundry_deployment_map = deploymentMap;
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
    return <div className="settings-page"><p>Loading configuration...</p></div>;
  }

  const deploymentNames = deployments.map((d) => d.name).filter(Boolean);

  return (
    <div className="settings-page">
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
          <h3>Azure Foundry Connection</h3>
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
          <option value="peer_review">Peer Review</option>
          <option value="consensus_only">Consensus Only</option>
          <option value="chairman_only">Chairman Only</option>
          <option value="red_team">Red Team</option>
          <option value="audience_split">Audience Split</option>
          <option value="claim_evidence">Claim Evidence</option>
        </select>
        <label className="settings-label">Ranking Aggregation</label>
        <select
          className="settings-select"
          value={rankingAggregation}
          onChange={(e) => setRankingAggregation(e.target.value)}
        >
          <option value="average_rank">Average Rank</option>
          <option value="borda">Borda Count</option>
        </select>
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
  );
}
