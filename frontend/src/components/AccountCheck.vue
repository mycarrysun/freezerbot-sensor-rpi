<template>
  <div class="account-check">
    <h2>Freezerbot Account Required</h2>

    <div class="button-container">
      <Button label="I Have an Account Already"
              color="primary"
              @click="continueSetup"
      />

      <Button label="I need a new account"
              color="secondary"
              @click="showingAccountInfo = true"
      />
    </div>

    <template v-if="showingAccountInfo">
      <div class="step">
        <div class="step-number">1</div>
        <div class="step-content">
          <h3>Create a Freezerbot Account</h3>
          <p>You'll need to temporarily disconnect from this WiFi network to create an account.</p>

          <div class="instruction-box">
            <div class="highlight-url">setup.freezerbot.com</div>

            <h4>Instructions:</h4>
            <ol>
              <li><strong>Remember</strong> the website above</li>
              <li>Exit this page and <strong>disconnect</strong> from "Freezerbot-Setup" WiFi</li>
              <li>Open your browser and visit <strong style="color: var(--primary-color)">setup.freezerbot.com</strong></li>
              <li>Create your account and make note of your email and password</li>
              <li>Scan the QR Code again to get back to this page (you may have to click "Sign in to Network")</li>
            </ol>
          </div>

          <div class="action-buttons">
            <Button label="Copy Website to Clipboard" color="neutral" class="copy-button" @click="copyToClipboard"/>
            <div v-if="copied" class="copied-message">Copied!</div>
          </div>
        </div>
      </div>

      <div class="step">
        <div class="step-number">2</div>
        <div class="step-content">
          <h3>Already Have an Account?</h3>
          <p>If you've already created an account on the Freezerbot app, you can continue with setup.</p>
          <Button label="Continue to Setup" @click="continueSetup"/>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import Button from '@/components/Button.vue'

const emit = defineEmits<{
  (e: 'continue-to-setup'): void;
}>();

const copied = ref(false);
const showingAccountInfo = ref(false);

function continueSetup() {
  emit('continue-to-setup');
}

function copyToClipboard() {
  navigator.clipboard.writeText('https://setup.freezerbot.com')
    .then(() => {
      copied.value = true;
      setTimeout(() => {
        copied.value = false;
      }, 2000);
    })
    .catch(() => {
      alert('Unable to copy to clipboard. Please go to the website: setup.freezerbot.com');
    });
}
</script>

<style scoped>
.button-container  {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  margin-bottom: 1.5rem;
}
.account-check {
  text-align: center;
  margin-bottom: 30px;
}

h2 {
  margin-bottom: 25px;
  color: var(--primary-color);
}

.step {
  display: flex;
  align-items: flex-start;
  padding: 15px;
  margin-bottom: 10px;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  background-color: var(--background-color);
  text-align: left;
}

.step-number {
  background-color: var(--primary-color);
  color: white;
  width: 30px;
  height: 30px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: bold;
  margin-right: 15px;
  flex-shrink: 0;
}

.step-content {
  flex: 1;
}

.step-content h3 {
  margin-top: 0;
  margin-bottom: 10px;
}

.highlight-url {
  font-size: 20px;
  text-align: center;
  font-weight: bold;
  background-color: #fff3cd;
  color: #856404;
  padding: 12px;
  border-radius: 6px;
  margin: 15px 0;
  border: 2px dashed #ffeeba;
  word-break: break-all;
}

.instruction-box {
  padding: 15px;
  margin-top: 10px;
}

.instruction-box h4 {
  margin-top: 0;
  margin-bottom: 10px;
}

.instruction-box ol {
  margin-left: 20px;
  padding-left: 0;
  line-height: 1.5;
}

.instruction-box li {
  margin-bottom: 8px;
}

.action-buttons {
  margin-top: 15px;
  position: relative;
}

.copied-message {
  position: absolute;
  bottom: -25px;
  left: 50%;
  transform: translateX(-50%);
  background-color: #4CAF50;
  color: white;
  padding: 5px 10px;
  border-radius: 3px;
  font-size: 12px;
}

.copy-button {
  display: flex;
  margin: 0 auto;
}

@media (max-width: 480px) {
  .step {
    flex-direction: column;
  }

  .step-number {
    margin-bottom: 10px;
  }
}
</style>