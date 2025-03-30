<template>
  <form @submit.prevent="submitForm">
    <div class="step">
      <label for="wifi_ssid">WiFi Network Name:</label>
      <input type="text" id="wifi_ssid" v-model="formData.wifi_ssid" required>
      <button type="button" @click="scanWifi" class="secondary-button">Scan for Networks</button>

      <div v-if="showNetworkList" class="wifi-list">
        <div v-if="isScanning" class="spinner"></div>
        <div v-else-if="wifiScanningError" class="error-message">{{ wifiScanningError }}</div>
        <div v-else>
          <div
            v-for="network in networks"
            :key="network"
            class="wifi-option"
            @click="selectNetwork(network)"
          >
            {{ network }}
          </div>
        </div>
      </div>
    </div>

    <div class="step">
      <label for="wifi_password">WiFi Password:</label>
      <input type="password" id="wifi_password" v-model="formData.wifi_password" required>
    </div>

    <div class="step">
      <label for="api_token">Freezerbot API Token:</label>
      <input type="text" id="api_token" v-model="formData.api_token" required>
      <p class="hint">You can find this in your welcome email or on your Freezerbot account page</p>
    </div>

    <div class="step">
      <label for="freezer_name">Freezer Name (Optional):</label>
      <input type="text" id="freezer_name" v-model="formData.freezer_name" placeholder="e.g., Lab Freezer 1">
    </div>

    <div v-if="formError" class="error-message">{{ formError }}</div>

    <button type="submit" :disabled="isSubmitting" class="primary-button">
      <span v-if="isSubmitting">Setting up...</span>
      <span v-else>Set Up My Freezerbot</span>
    </button>
  </form>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue';

interface FormData {
  wifi_ssid: string;
  wifi_password: string;
  api_token: string;
  freezer_name: string;
}

interface ApiResponse {
  success: boolean;
  error?: string;
  networks?: string[];
}

const emit = defineEmits<{
  (e: 'setup-completed'): void;
}>();

const formData = reactive<FormData>({
  wifi_ssid: '',
  wifi_password: '',
  api_token: '',
  freezer_name: ''
});

const networks = ref<string[]>([]);
const showNetworkList = ref<boolean>(false);
const isScanning = ref<boolean>(false);
const isSubmitting = ref<boolean>(false);
const wifiScanningError = ref<string>('');
const formError = ref<string>('');

async function scanWifi() {
  showNetworkList.value = true;
  isScanning.value = true;
  wifiScanningError.value = '';

  try {
    const response = await fetch('/api/scan-wifi');
    const data = await response.json() as ApiResponse;

    if (data.error) {
      wifiScanningError.value = data.error;
    } else {
      networks.value = data.networks || [];
      if (networks.value.length === 0) {
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

function selectNetwork(network: string) {
  formData.wifi_ssid = network;
  showNetworkList.value = false;
}

async function submitForm() {
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
input[type="text"], input[type="password"] {
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
  margin-top: 5px;
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
</style>