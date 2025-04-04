<template>
  <form @submit.prevent="submitForm">
    <div class="step">
      <label for="deviceName">Sensor name:</label>
      <input id="deviceName" type="text" v-model="formData.deviceName" required>
      <p class="hint">This will name the sensor in the Freezerbot app</p>
    </div>

    <div class="networks-container">
      <h3>WiFi Networks</h3>
      <div v-for="(network, index) in formData.networks" :key="index" class="network-entry">
        <div class="network-header">
          <h4>Network {{ index + 1 }}</h4>
          <button
            v-if="formData.networks.length > 1"
            type="button"
            @click="removeNetwork(index)"
            class="remove-button"
          >
            Remove
          </button>
        </div>

        <div class="step">
          <label :for="`wifi_ssid_${index}`">WiFi Network Name:</label>
          <div class="input-with-button">
            <input
              type="text"
              :id="`wifi_ssid_${index}`"
              v-model="network.ssid"
              required
            >
            <button
              type="button"
              @click="scanWifi(index)"
              class="secondary-button"
            >
              Scan
            </button>
          </div>

          <div v-if="showNetworkList === index" class="wifi-list">
            <div v-if="isScanning" class="spinner"></div>
            <div v-else-if="wifiScanningError" class="error-message">{{ wifiScanningError }}</div>
            <div v-else>
              <div
                v-for="availableNetwork in availableNetworks"
                :key="availableNetwork"
                class="wifi-option"
                @click="selectNetwork(availableNetwork, index)"
              >
                {{ availableNetwork }}
              </div>
            </div>
          </div>
        </div>

        <div class="step">
          <label :for="`wifi_password_${index}`">WiFi Password:</label>
          <div class="input-with-button">
            <input
              :type="showingPassword.includes(index) ? 'text' : 'password'"
              :id="`wifi_password_${index}`"
              v-model="network.password"
              required
            >
            <button type="button"
                    class="secondary-button"
                    @click="togglePassword(index)"
            >
              {{showingPassword.includes(index) ? 'Hide': 'Show'}}
            </button>
          </div>

        </div>

        <div v-if="network.enterprise" class="enterprise-settings">
          <div class="enterprise-badge">Enterprise Network</div>
          <div class="step">
            <label :for="`username_${index}`">Username:</label>
            <input
              type="text"
              :id="`username_${index}`"
              v-model="network.username"
              required
            >
          </div>
        </div>
      </div>

      <button
        type="button"
        @click="addNetwork"
        class="secondary-button add-network-button"
      >
        Add Another Network
      </button>
    </div>

    <div class="step">
      <label for="email">Freezerbot Email:</label>
      <input type="email" id="email" v-model="formData.email" required>
      <p class="hint">What you use to login to the Freezerbot App</p>
    </div>

    <div class="step">
      <label for="password">Freezerbot Password:</label>
      <input id="password" type="password" v-model="formData.password" required>
    </div>

    <div v-if="formError" class="error-message">{{ formError }}</div>

    <button type="submit" :disabled="isSubmitting" class="primary-button">
      <span v-if="isSubmitting">Setting up...</span>
      <span v-else>Set Up My Freezerbot</span>
    </button>
  </form>
</template>

<script setup lang="ts">
import { ref, reactive, watch } from 'vue';

interface WiFiNetwork {
  ssid: string;
  password: string;
  enterprise: boolean;
  username?: string;
  eap_method?: string;
  phase2_auth?: string;
}

interface FreezerbotConfig {
  networks: WiFiNetwork[];
  email: string;
  password: string;
  deviceName: string;
  error?: string;
}

interface ApiResponse {
  success: boolean;
  error?: string;
  networks?: string[];
}

const emit = defineEmits<{
  (e: 'setup-completed'): void;
}>();

const formData = reactive<FreezerbotConfig>({
  networks: [{
    ssid: '',
    password: '',
    enterprise: false,
    username: '',
    eap_method: 'peap',
    phase2_auth: 'mschapv2'
  }],
  deviceName: '',
  email: '',
  password: '',
});

const availableNetworks = ref<string[]>([]);
const showNetworkList = ref<number | null>(null);
const showingPassword = ref<number[]>([]);
const isScanning = ref<boolean>(false);
const isSubmitting = ref<boolean>(false);
const wifiScanningError = ref<string>('');
const formError = ref<string>('');

watch(() => formData.email, () => {
  formError.value = '';
})

watch(() => formData.password, () => {
  formError.value = '';
})

function addNetwork() {
  formData.networks.push({
    ssid: '',
    password: '',
    enterprise: false,
    username: '',
    eap_method: 'peap',
    phase2_auth: 'mschapv2'
  });
}

function togglePassword(index: number) {
  if(!showingPassword.value.includes(index)) {
    showingPassword.value.push(index);
  }else{
    const thisIndex = showingPassword.value.indexOf(index);
    showingPassword.value.splice(thisIndex, 1);
  }
}

function removeNetwork(index: number) {
  formData.networks.splice(index, 1);
}

async function getCurrentConfig() {
  const response = await fetch('/api/get-config');
  const data = await response.json() as FreezerbotConfig;

  if(data.networks){
    formData.networks = data.networks;
  }

  if(data.email){
    formData.email = data.email;
  }

  if(data.password){
    formData.password = data.password;
  }

  if(data.error){
    formError.value = data.error;
  }
}

async function scanWifi(networkIndex: number) {
  showNetworkList.value = networkIndex;
  isScanning.value = true;
  wifiScanningError.value = '';

  try {
    const response = await fetch('/api/scan-wifi');
    const data = await response.json() as ApiResponse;

    if (data.error) {
      wifiScanningError.value = data.error;
    } else {
      availableNetworks.value = data.networks || [];
      if (availableNetworks.value.length === 0) {
        wifiScanningError.value = 'No networks found. Please check that WiFi is enabled on your device.';
      }
    }
  } catch (err) {
    wifiScanningError.value = 'Failed to scan networks. Please try again or enter network name manually.';
    console.error('Error scanning WiFi:', err);
  } finally {
    isScanning.value = false;
  }
}

function selectNetwork(networkName: string, networkIndex: number) {
  formData.networks[networkIndex].ssid = networkName;
  showNetworkList.value = null;
}

async function submitForm() {
  // Validate that we have at least one network with SSID and password
  if (formData.networks.length === 0 ||
      !formData.networks.some(network => network.ssid && network.password)) {
    formError.value = 'At least one WiFi network with SSID and password is required';
    return;
  }

  if(!formData.email || !formData.password){
    formError.value = 'Please provide your Freezerbot email and password.';
    return;
  }

  if(!formData.deviceName){
    formError.value = 'Please provide a name for your Freezerbot sensor.';
  }

  isSubmitting.value = true;
  formError.value = '';

  try {
    const response = await fetch('/api/setup', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(formData)
    });

    const result = await response.json() as ApiResponse;

    if (result.success) {
      emit('setup-completed');
    } else {
      formError.value = result.error || 'Setup failed. Please try again.';
    }
  } catch (err) {
    formError.value = 'Connection error. Please try again.';
    console.error('Error submitting form:', err);
  } finally {
    isSubmitting.value = false;
  }
}

getCurrentConfig();
</script>

<style scoped>
.step {
  margin-bottom: 20px;
}
label {
  display: block;
  margin-bottom: 5px;
  font-weight: bold;
}
input[type="text"], input[type="password"], input[type="email"], select {
  width: 100%;
  padding: 10px;
  border: 1px solid #ddd;
  border-radius: 5px;
  font-size: 16px;
  box-sizing: border-box;
}
.hint {
  margin-top: 5px;
  font-size: 14px;
  color: #666;
}
.networks-container {
  border: 1px solid #eee;
  border-radius: 5px;
  padding: 15px;
  margin-bottom: 20px;
  background-color: #f9f9f9;
}
.network-entry {
  padding: 15px;
  margin-bottom: 15px;
  border: 1px solid #e0e0e0;
  border-radius: 5px;
  background-color: white;
}
.network-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}
.network-header h4 {
  margin: 0;
}
.remove-button {
  background-color: #f44336;
  color: white;
  border: none;
  padding: 5px 10px;
  border-radius: 3px;
  cursor: pointer;
  font-size: 12px;
}
.remove-button:hover {
  background-color: #d32f2f;
}
.add-network-button {
  width: 100%;
  margin-top: 10px;
}
.input-with-button {
  display: flex;
  gap: 5px;
}
.input-with-button input {
  flex-grow: 1;
}
.primary-button {
  background-color: #0066cc;
  color: white;
  border: none;
  padding: 12px 20px;
  border-radius: 5px;
  font-size: 16px;
  cursor: pointer;
  width: 100%;
  margin-top: 20px;
}
.primary-button:hover {
  background-color: #0055aa;
}
.primary-button:disabled {
  background-color: #cccccc;
  cursor: not-allowed;
}
.secondary-button {
  background-color: #f0f0f0;
  color: #333;
  border: 1px solid #ddd;
  padding: 8px 12px;
  border-radius: 5px;
  font-size: 14px;
  cursor: pointer;
}
.secondary-button:hover {
  background-color: #e0e0e0;
}
.wifi-list {
  max-height: 150px;
  overflow-y: auto;
  border: 1px solid #ddd;
  border-radius: 5px;
  margin-top: 10px;
}
.wifi-option {
  padding: 10px;
  border-bottom: 1px solid #eee;
  cursor: pointer;
}
.wifi-option:hover {
  background-color: #f5f5f5;
}
.spinner {
  border: 4px solid #f3f3f3;
  border-top: 4px solid #0066cc;
  border-radius: 50%;
  width: 30px;
  height: 30px;
  animation: spin 2s linear infinite;
  margin: 20px auto;
}
@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}
.error-message {
  color: #F44336;
  margin-top: 10px;
  padding: 10px;
  background-color: #FFEBEE;
  border-radius: 5px;
}
.enterprise-settings {
  margin-top: 10px;
  padding: 15px;
  background-color: #f5f9ff;
  border-radius: 5px;
  border: 1px solid #d5e3ff;
}
.enterprise-badge {
  display: inline-block;
  background-color: #0066cc;
  color: white;
  padding: 5px 10px;
  border-radius: 3px;
  font-size: 12px;
  margin-bottom: 15px;
}
</style>