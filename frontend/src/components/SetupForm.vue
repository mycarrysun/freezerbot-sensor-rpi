<template>
  <form @submit.prevent="submitForm">
    <div class="panel">
      <h3>Please note: You must have an existing Freezerbot account to continue</h3>
      <Button class="primary-button"
              href="https://app.freezerbot.com/register"
              target="_blank"
              @click="createAccount"
              label="Create Account"
      />
    </div>
    <div class="step">
      <label for="device_name">What will you call this sensor?</label>
      <input id="device_name" type="text" v-model="formData.device_name" required>
      <p class="hint">This will be the name you see for this sensor in the Freezerbot app (eg. Lab Freezer, Store Room, Kitchen Fridge)</p>
    </div>

    <div class="step">
      <h3 style="margin-top: 2rem">WiFi Networks</h3>
      <p class="hint">Please enter all of the WiFi networks that this sensor can use to connect to the internet. You can enter multiple even if you are not near them right now, as long as you know the WiFi Network Name (SSID).</p>

      <div v-for="(network, index) in formData.networks" :key="index" class="network-entry">
        <div class="network-header">
          <h4>Network {{ index + 1 }}</h4>
          <Button
            v-if="formData.networks.length > 1"
            type="button"
            color="danger"
            label="Remove"
            @click="removeNetwork(index)"
          />
        </div>

        <label :for="`wifi_ssid_${index}`">WiFi Network Name:</label>
        <div class="input-with-button">
          <input
            type="text"
            :id="`wifi_ssid_${index}`"
            v-model="network.ssid"
            required
          >
          <Button
            type="button"
            @click="scanWifi(index)"
            label="Scan"
            color="secondary"
          />
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

        <label :for="`wifi_password_${index}`" style="margin-top: 1rem">WiFi Password:</label>
        <div class="input-with-button">
          <input
            :type="showingPassword.includes(index) ? 'text' : 'password'"
            :id="`wifi_password_${index}`"
            v-model="network.password"
            required
          >
          <Button type="button"
                  color="neutral"
                  :label="showingPassword.includes(index) ? 'Hide': 'Show'"
                  @click="toggleWifiPassword(index)"
          />
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

      <Button
        type="button"
        @click="addNetwork"
        color="primary"
        label="Add Another Network"
      />
    </div>

    <div class="step">
      <label for="email">Freezerbot Email:</label>
      <input type="email" id="email" v-model="formData.email" required>
      <p class="hint">What you use to login to the Freezerbot App</p>

      <label for="password">Freezerbot Password:</label>
      <div class="input-with-button">
        <input id="password"
               :type="showingFreezerbotPassword ? 'text' : 'password'"
               v-model="formData.password"
               required
        >
        <Button :label="showingFreezerbotPassword ? 'Hide' : 'Show'" type="button" @click="togglePassword" color="neutral"/>
      </div>
    </div>

    <div v-if="formError" class="error-message">{{ formError }}</div>

    <Button type="submit"
            :disabled="isSubmitting"
            class="primary-button"
            :label="isSubmitting ? 'Setting up...' : 'Setup my sensor'"/>
  </form>
</template>

<script setup lang="ts">
import { ref, reactive, watch } from 'vue';
import Button from '@/components/Button.vue'

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
  device_name: string;
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
  device_name: '',
  email: '',
  password: '',
});

const availableNetworks = ref<string[]>([]);
const showNetworkList = ref<number | null>(null);
const showingPassword = ref<number[]>([]);
const showingFreezerbotPassword = ref<boolean>(false);
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

function createAccount() {
  fetch('/api/create-account', {method: 'POST'});
}

function toggleWifiPassword(index: number) {
  if(!showingPassword.value.includes(index)) {
    showingPassword.value.push(index);
  }else{
    const thisIndex = showingPassword.value.indexOf(index);
    showingPassword.value.splice(thisIndex, 1);
  }
}
function togglePassword() {
  showingFreezerbotPassword.value = !showingFreezerbotPassword.value;
}

function removeNetwork(index: number) {
  formData.networks.splice(index, 1);
}

async function getCurrentConfig() {
  const response = await fetch('/api/get-config');
  const data = await response.json() as FreezerbotConfig;

  if(data.device_name){
    formData.device_name = data.device_name;
  }

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

  if(!formData.device_name){
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

<style scoped lang="scss">
.step {
  margin-bottom: 3rem;
}
h1, h2, h3, h4, h5, h6 {
  margin-top: 0.1em;
  margin-bottom: 0.1em;
}
label {
  display: block;
  margin-bottom: 5px;
  font-weight: bold;
}
input[type="text"], input[type="password"], input[type="email"], select {
  width: 100%;
  padding: 10px;
  border: 1px solid var(--border-color);
  color: var(--text-color);
  font-family: 'Inter', Arial, sans-serif;
  border-radius: 5px;
  font-size: 16px;
  box-sizing: border-box;
  background: var(--background-color);

  &:focus-within, &:active, &:focus, &:focus-visible {
    border-color: var(--border-focus-color);
    outline: 2px solid var(--border-focus-color);
    outline-offset: -2px;
  }
}

.panel {
  background-color: #4dbbff33;
  color: #0083e5;
  padding: 1rem 1.5rem;
  margin-bottom: 2rem;
  border-left: solid 4px #0083e5;

  h3 {
    margin: 0;
  }

  a {
    display: inline-flex;
    margin: 1rem 0 0.5rem;
  }
}

.hint {
  margin-top: 5px;
  font-size: 14px;
  color: var(--hint-color);
}
.network-entry {
  padding: 15px;
  margin-bottom: 15px;
  border: 1px solid var(--border-color);
  border-radius: 5px;
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
  border-top: 4px solid var(--primary-color);
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
  color: var(--danger-color);
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
  background-color: var(--primary-color);
  color: white;
  padding: 5px 10px;
  border-radius: 3px;
  font-size: 12px;
  margin-bottom: 15px;
}
</style>